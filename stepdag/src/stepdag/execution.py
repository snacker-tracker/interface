"""Running one asset's step, and running a whole graph in one process."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from stepdag.assets import RESERVED_NAMES, Bindings, Definitions
from stepdag.io import UNCHANGED, Pointer, RunContext


class StepFailed(Exception):
    """An asset's step can't produce a pointer. Step Functions sees the class name as the error."""


class CheckFailed(Exception):
    """An asset's value failed one or more of its blocking checks, so it wasn't stored."""

    def __init__(self, asset: str, failures: dict[str, str]) -> None:
        self.asset = asset
        self.failures = failures
        super().__init__(f"{asset} failed its checks: " + "; ".join(f"{k}: {v}" for k, v in failures.items()))


class PlanFailed(Exception):
    """A run's config doesn't fit the graph, found before any asset runs."""


@dataclass(frozen=True)
class Run:
    """What every step of a run needs to know about it."""

    run_id: str
    started_at: str
    config: dict[str, Any]
    """The whole run config, sections included."""
    selected: list[str]
    """The assets this run materializes, downstream ones included. The others re-emit their latest."""

    def to_json(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "started_at": self.started_at, "config": self.config, "selected": self.selected}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Run":
        return cls(data["run_id"], data["started_at"], data["config"], list(data["selected"]))


def plan(definitions: Definitions, io_managers: Bindings, config: Mapping[str, Any], run_id: str, started_at: str) -> Run:
    """Resolve a run's selection, and check it against the graph before any asset runs."""
    names = definitions.names
    selection = config.get("select")
    if selection is None:
        selected = set(names)
    else:
        if unknown := sorted(set(selection) - set(names)):
            raise PlanFailed(f"selected assets don't exist: {', '.join(unknown)}")
        selected = definitions.downstream(selection) if config.get("downstream") else set(selection)
    missing = sorted(n for n in names if n not in selected and io_managers[definitions[n].io_manager].latest(n) is None)
    if missing:
        raise PlanFailed(f"unselected assets have no materialization to re-emit: {', '.join(missing)}")
    return Run(run_id, started_at, dict(config), [n for n in names if n in selected])


@dataclass(frozen=True)
class Outcome:
    pointer: Pointer
    computed: bool
    """False when the step re-emitted the asset's latest materialization."""


def materialize(definitions: Definitions, name: str, pointers: Mapping[str, Pointer], run: Run, io_managers: Bindings) -> Outcome:
    """Run one asset's step: load its parents, call its function, and store the result."""
    a = definitions[name]
    io_manager = io_managers[a.io_manager]
    context = _context(definitions, name, run)
    latest = io_manager.latest(name)
    if name not in run.selected:
        if latest is None:
            raise StepFailed(f"{name} isn't selected and has no materialization to re-emit")
        return Outcome(latest, computed=False)
    parents = [io_managers[pointers[dep].io_manager].load(pointers[dep]) for dep in a.deps]
    keywords: dict[str, Any] = {}
    if a.wants_context:
        keywords["context"] = context
    if a.wants_previous:
        keywords["previous"] = None if latest is None or context.force else io_manager.load(latest)
    value = a.fn(*parents, **keywords)
    if value is UNCHANGED:
        if context.force:
            raise StepFailed(f"{name} returned UNCHANGED in a forced run, which skips nothing")
        if latest is None:
            raise StepFailed(f"{name} returned UNCHANGED but has no materialization to re-emit")
        return Outcome(latest, computed=False)
    failures = {check.__name__: message for check in a.checks if (message := check(value, context)) is not None}
    if failures:
        raise CheckFailed(name, failures)
    return Outcome(io_manager.store(value, name, context), computed=True)


def _context(definitions: Definitions, name: str, run: Run) -> RunContext:
    names = set(definitions.names)
    shared = {k: v for k, v in run.config.items() if k not in names and k not in RESERVED_NAMES}
    return RunContext(
        run_id=run.run_id,
        started_at=run.started_at,
        asset=name,
        config=shared,
        asset_config=dict(run.config.get(name, {})),
        force=bool(run.config.get("force", False)),
    )


@dataclass
class RunResult:
    run_id: str
    pointers: dict[str, Pointer] = field(default_factory=dict)
    computed: list[str] = field(default_factory=list)
    """The assets whose values were stored, in the order they ran."""
    skipped: list[str] = field(default_factory=list)
    """The assets that re-emitted their latest materialization."""


def run(
    definitions: Definitions,
    io_managers: Bindings,
    config: Mapping[str, Any] | None = None,
    *,
    select: list[str] | None = None,
    downstream: bool = False,
    force: bool = False,
    started_at: datetime | None = None,
) -> RunResult:
    """Run the graph in this process, passing pointers between assets as Step Functions would.

    `select`, `downstream` and `force` are the run config's own keys, given separately for convenience.
    `started_at` fixes the run's start time (default: now), so a graph can be built at a known `now`.
    """
    started = started_at or datetime.now(UTC)
    run_id = f"local-{started:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    config = dict(config or {})
    if select is not None:
        config["select"] = select
    if downstream:
        config["downstream"] = True
    if force:
        config["force"] = True
    the_run = plan(definitions, io_managers, config, run_id, started.isoformat())
    result = RunResult(run_id)
    for level in definitions.levels:
        for name in level:
            # Round-trip through JSON, as the state machine's state would, so local runs exercise it too.
            pointers = {k: Pointer.from_json(p.to_json()) for k, p in result.pointers.items()}
            outcome = materialize(definitions, name, pointers, the_run, io_managers)
            result.pointers[name] = outcome.pointer
            (result.computed if outcome.computed else result.skipped).append(name)
    return result

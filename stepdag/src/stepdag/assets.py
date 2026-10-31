"""Declaring assets, and collecting them into a graph."""

import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from stepdag.io import IOManager

# Execution-input keys stepdag reads itself, so no asset may take their names.
RESERVED_NAMES = frozenset({"force", "select", "downstream"})


class DefinitionError(Exception):
    """An asset or a graph that can't be run."""


@dataclass(frozen=True)
class Asset:
    name: str
    fn: Callable[..., Any]
    deps: tuple[str, ...]
    io_manager: str
    memory: int
    timeout: int
    ephemeral_storage: int
    retry_attempts: int
    role: str
    checks: tuple[Callable[..., str | None], ...]
    wants_previous: bool
    wants_context: bool


def asset(
    *,
    deps: Sequence[str] = (),
    io_manager: str,
    memory: int = 512,
    timeout: int = 60,
    ephemeral_storage: int = 512,
    retry_attempts: int = 0,
    role: str = "default",
    checks: Sequence[Callable[..., str | None]] = (),
) -> Callable[[Callable[..., Any]], Asset]:
    """Declare an asset computed by the decorated function from the values of `deps`, in order.

    The function may also declare keyword-only `previous` and `context` parameters.
    `retry_attempts` retries the function's own errors; transient Lambda errors are always retried.
    """

    def declare(fn: Callable[..., Any]) -> Asset:
        name = fn.__name__
        if name in RESERVED_NAMES or name.startswith("_"):
            raise DefinitionError(f"{name}: asset names can't start with '_' or be one of {sorted(RESERVED_NAMES)}")
        parameters = inspect.signature(fn).parameters.values()
        positional = [p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        keyword = {p.name for p in parameters if p.kind == p.KEYWORD_ONLY}
        if len(positional) != len(deps):
            raise DefinitionError(f"{name}: has {len(deps)} deps but its function takes {len(positional)} parents")
        if unknown := keyword - {"previous", "context"}:
            raise DefinitionError(f"{name}: unknown keyword-only parameters {sorted(unknown)}")
        return Asset(
            name=name,
            fn=fn,
            deps=tuple(deps),
            io_manager=io_manager,
            memory=memory,
            timeout=timeout,
            ephemeral_storage=ephemeral_storage,
            retry_attempts=retry_attempts,
            role=role,
            checks=tuple(checks),
            wants_previous="previous" in keyword,
            wants_context="context" in keyword,
        )

    return declare


Bindings = Mapping[str, IOManager]


@dataclass(frozen=True)
class Definitions:
    """A graph of assets, and the IO manager bindings of each environment it runs in.

    `environments` maps an environment's name, such as "local" or "lambda", to a function
    that builds its bindings, so each can read its settings (a directory, a bucket) when it runs.
    """

    assets: Iterable[Asset]
    environments: Mapping[str, Callable[[], Bindings]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        by_name: dict[str, Asset] = {}
        for a in self.assets:
            if a.name in by_name:
                raise DefinitionError(f"{a.name}: defined twice")
            by_name[a.name] = a
        for a in by_name.values():
            for dep in a.deps:
                if dep not in by_name:
                    raise DefinitionError(f"{a.name}: depends on unknown asset {dep}")
        object.__setattr__(self, "assets", tuple(by_name.values()))
        object.__setattr__(self, "_by_name", by_name)
        object.__setattr__(self, "_levels", _levels(by_name))

    def __getitem__(self, name: str) -> Asset:
        by_name: dict[str, Asset] = getattr(self, "_by_name")
        return by_name[name]

    @property
    def names(self) -> list[str]:
        return [a.name for a in self.assets]

    @property
    def levels(self) -> list[list[str]]:
        """The assets in dependency order, grouped so that each group depends only on earlier ones."""
        levels: list[list[str]] = getattr(self, "_levels")
        return levels

    def downstream(self, names: Iterable[str]) -> set[str]:
        """The named assets and every asset that depends on them, directly or not."""
        found = set(names)
        for level in self.levels:
            for name in level:
                if found.intersection(self[name].deps):
                    found.add(name)
        return found

    def bindings(self, environment: str) -> Bindings:
        if environment not in self.environments:
            raise DefinitionError(f"no bindings for the {environment!r} environment")
        return self.environments[environment]()


def _levels(by_name: Mapping[str, Asset]) -> list[list[str]]:
    levels: list[list[str]] = []
    placed: set[str] = set()
    remaining = dict(by_name)
    while remaining:
        ready = sorted(name for name, a in remaining.items() if placed.issuperset(a.deps))
        if not ready:
            raise DefinitionError(f"cycle among {sorted(remaining)}")
        levels.append(ready)
        placed.update(ready)
        for name in ready:
            del remaining[name]
    return levels

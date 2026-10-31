"""The Lambda handlers the manifest's functions run: one plans a run, the other runs any asset's step.

Both read `STEPDAG_DEFINITIONS` (module:attribute) and bind IO managers from its "lambda"
environment. The asset handler also reads `STEPDAG_ASSET`.
"""

import functools
import importlib
import os
from typing import Any

from stepdag.assets import Bindings, Definitions
from stepdag.execution import Run, materialize, plan
from stepdag.io import Pointer


@functools.cache
def _loaded(reference: str) -> tuple[Definitions, Bindings]:
    module_name, _, attribute = reference.partition(":")
    definitions = getattr(importlib.import_module(module_name), attribute)
    if not isinstance(definitions, Definitions):
        raise TypeError(f"{reference} is not a stepdag Definitions")
    return definitions, definitions.bindings("lambda")


def plan_handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    """Turn the execution input into the run's state: `{"run": ..., "pointers": {}}`."""
    definitions, io_managers = _loaded(os.environ["STEPDAG_DEFINITIONS"])
    run = plan(definitions, io_managers, event["config"] or {}, event["run_id"], event["started_at"])
    return {"run": run.to_json(), "pointers": {}}


def asset_handler(event: dict[str, Any] | list[dict[str, Any]], _context: object) -> dict[str, Any]:
    """Run one asset's step, and return the state with its pointer added.

    After a Parallel state the event is a list of its branches' states, which are merged first.
    """
    definitions, io_managers = _loaded(os.environ["STEPDAG_DEFINITIONS"])
    name = os.environ["STEPDAG_ASSET"]
    state = _merged(event)
    pointers = {k: Pointer.from_json(p) for k, p in state["pointers"].items()}
    outcome = materialize(definitions, name, pointers, Run.from_json(state["run"]), io_managers)
    print(f"{name}: {'stored' if outcome.computed else 're-emitted'} {outcome.pointer.uri}")
    return {"run": state["run"], "pointers": {**state["pointers"], name: outcome.pointer.to_json()}}


def _merged(event: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(event, dict):
        return event
    pointers: dict[str, Any] = {}
    for branch in event:
        pointers.update(branch["pointers"])
    return {"run": event[0]["run"], "pointers": pointers}

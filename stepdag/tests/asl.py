"""A small Amazon States Language interpreter, enough to run a stepdag manifest against the real handlers.

It knows Task states that invoke a Lambda (Parameters with `$` and `$$.Execution.*` paths, and
`OutputPath: $.Payload`) and Parallel states, and ignores retries. Each function runs in this
process with its manifest environment, as its own Lambda would.
"""

import importlib
import os
from typing import Any

from stepdag.manifest import PREFIX


class ExecutionFailed(Exception):
    def __init__(self, state: str, error: BaseException) -> None:
        self.state = state
        self.error = type(error).__name__
        self.cause = str(error)
        super().__init__(f"{state}: {self.error}: {self.cause}")


def execute(manifest: dict[str, Any], execution_input: Any, name: str, started_at: str = "2026-10-30T00:00:00Z") -> Any:
    execution = {"Name": name, "StartTime": started_at}
    machine = manifest["state_machine"]
    return _run(machine["StartAt"], machine["States"], execution_input, manifest, execution)


def _run(start: str, states: dict[str, Any], data: Any, manifest: dict[str, Any], execution: dict[str, str]) -> Any:
    name: str | None = start
    while name is not None:
        state = states[name]
        if state["Type"] == "Task":
            data = _task(name, state, data, manifest, execution)
        elif state["Type"] == "Parallel":
            data = [_run(b["StartAt"], b["States"], data, manifest, execution) for b in state["Branches"]]
        else:
            raise NotImplementedError(state["Type"])
        name = None if state.get("End") else state["Next"]
    return data


def _task(name: str, state: dict[str, Any], data: Any, manifest: dict[str, Any], execution: dict[str, str]) -> Any:
    assert state["Resource"] == "arn:aws:states:::lambda:invoke"
    assert state["OutputPath"] == "$.Payload"
    parameters = state["Parameters"]
    function = manifest["functions"][parameters["FunctionName"].removeprefix(PREFIX)]
    payload = data if "Payload.$" in parameters else _resolve(parameters["Payload"], data, execution)
    module, _, attribute = function["handler"].rpartition(".")
    handler = getattr(importlib.import_module(module), attribute)
    saved = dict(os.environ)
    os.environ.update(function["environment"])
    try:
        return handler(payload, None)
    except Exception as error:
        raise ExecutionFailed(name, error) from error
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _resolve(template: dict[str, Any], data: Any, execution: dict[str, str]) -> dict[str, Any]:
    resolved = {}
    for key, value in template.items():
        if not key.endswith(".$"):
            resolved[key] = value
        elif value == "$":
            resolved[key.removesuffix(".$")] = data
        elif value.startswith("$$.Execution."):
            resolved[key.removesuffix(".$")] = execution[value.removeprefix("$$.Execution.")]
        else:
            raise NotImplementedError(value)
    return resolved

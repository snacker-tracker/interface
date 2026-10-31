"""A finished execution as a run file: what a page needs to draw the graph and its timeline.

Everything comes from the execution's description and history (GetExecutionHistory) and the graph's
definitions, so nothing in the state machine changes. Each step's output carries the run and every
pointer so far, which says each asset's status: a step that stored a value returns a pointer from
this run, and one that skipped re-emits an earlier run's. Pointers' URIs are left out, so the file
can be published.
"""

import json
from datetime import datetime
from typing import Any

from stepdag.assets import Definitions
from stepdag.manifest import PREFIX, render

FINISHED = ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED")


def report(definitions: Definitions, reference: str, execution: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """The run file of one execution (`DescribeExecution`'s fields) from its history events, oldest first."""
    asset_of_state = _asset_states(render(definitions, reference)["state_machine"]["States"])
    entered: dict[str, str] = {}
    exited: dict[str, tuple[str, dict[str, Any]]] = {}
    run: dict[str, Any] = {}
    failure: dict[str, Any] | None = None
    by_id = {event["id"]: event for event in history}

    for event in history:
        kind = event["type"]
        if kind == "TaskStateEntered":
            name = event["stateEnteredEventDetails"]["name"]
            if name in asset_of_state:
                entered[asset_of_state[name]] = _time(event["timestamp"])
        elif kind == "TaskStateExited":
            name = event["stateExitedEventDetails"]["name"]
            output = json.loads(event["stateExitedEventDetails"]["output"])
            if name == "plan":
                run = output["run"]
            elif name in asset_of_state:
                exited[asset_of_state[name]] = (_time(event["timestamp"]), output)
        elif kind == "TaskFailed":
            details = event["taskFailedEventDetails"]
            state = _state_of(event, by_id)
            step = asset_of_state.get(state, state) if state is not None else None
            failure = {"step": step, "error": details.get("error"), "cause": details.get("cause")}

    run_id = run.get("run_id", execution["name"])
    selected = set(run.get("selected", definitions.names))
    finished = execution["status"] in FINISHED

    assets = []
    for index, level in enumerate(definitions.levels):
        for name in level:
            asset = definitions[name]
            stopped, output = exited.get(name, (None, {}))
            metadata = output.get("pointers", {}).get(name, {}).get("metadata", {})
            if name in exited:
                status = "computed" if metadata.get("run_id") == run_id else "skipped"
                if name not in selected:
                    status = "not_selected"
            elif name in entered:
                status = "failed" if finished else "running"
            else:
                status = "not_run"
            assets.append({
                "name": name,
                "level": index,
                "deps": list(asset.deps),
                "io_manager": asset.io_manager,
                "status": status,
                "started_at": entered.get(name),
                "stopped_at": stopped,
                "version": metadata.get("version"),
                "written_by": metadata.get("run_id"),
            })

    return {
        "graph": reference,
        "run": {
            "id": run_id,
            "status": execution["status"],
            "started_at": _time(execution["startDate"]),
            "stopped_at": _time(execution["stopDate"]) if execution.get("stopDate") else None,
            "config": run.get("config", json.loads(execution.get("input") or "{}")),
            "error": failure if execution["status"] != "SUCCEEDED" else None,
        },
        "levels": definitions.levels,
        "assets": assets,
    }


def _asset_states(states: dict[str, Any]) -> dict[str, str]:
    """Each Task state's name, by the asset whose function it invokes, through Parallel branches."""
    found: dict[str, str] = {}
    for name, state in states.items():
        if state["Type"] == "Parallel":
            for branch in state["Branches"]:
                found.update(_asset_states(branch["States"]))
        elif state["Type"] == "Task":
            function = state["Parameters"]["FunctionName"].removeprefix(PREFIX)
            if not function.startswith("_"):
                found[name] = function
    return found


def _state_of(event: dict[str, Any], by_id: dict[int, dict[str, Any]]) -> str | None:
    """The state an event belongs to: Parallel branches interleave their events, so it's found by
    following `previousEventId` back to the state's TaskStateEntered, not by order."""
    current: dict[str, Any] | None = event
    while current is not None:
        if current["type"] == "TaskStateEntered":
            name: str = current["stateEnteredEventDetails"]["name"]
            return name
        previous = current.get("previousEventId")
        current = by_id.get(previous) if isinstance(previous, int) else None
    return None


def _time(value: str | datetime) -> str:
    """boto3 gives datetimes, the CLI's JSON gives strings; the file holds ISO 8601 strings."""
    return value.isoformat() if isinstance(value, datetime) else value


def latest_finished(client: Any, state_machine_arn: str, name: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The newest finished execution (or the one named), described, and its whole history."""
    if name is None:
        pages = client.get_paginator("list_executions").paginate(stateMachineArn=state_machine_arn)
        finished = (e for page in pages for e in page["executions"] if e["status"] in FINISHED)
        newest = next(finished, None)
        if newest is None:
            raise LookupError(f"{state_machine_arn} has no finished execution")
        execution_arn = newest["executionArn"]
    else:
        execution_arn = state_machine_arn.replace(":stateMachine:", ":execution:") + f":{name}"
    execution = client.describe_execution(executionArn=execution_arn)
    history = [
        event
        for page in client.get_paginator("get_execution_history").paginate(executionArn=execution_arn)
        for event in page["events"]
    ]
    return execution, history

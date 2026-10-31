"""The manifest: the state machine's definition and one function per asset, for Terraform to create.

Function names in the definition are `${function_prefix}<asset>`. Terraform replaces the
placeholder with its own prefix, so one manifest serves every environment.

The state that flows between steps is `{"run": ..., "pointers": {asset: pointer}}`. The plan
step makes it from the execution input. A Parallel state outputs a list of such states, one per
branch, and the next step's handler merges them.
"""

from typing import Any

from stepdag.assets import Asset, Definitions

PREFIX = "${function_prefix}"
PLAN = "_plan"
TRANSIENT_ERRORS = [
    "Lambda.ServiceException",
    "Lambda.AWSLambdaException",
    "Lambda.SdkClientException",
    "Lambda.TooManyRequestsException",
]
STEPDAG_ERRORS = ["CheckFailed", "PlanFailed", "StepFailed"]


def render(definitions: Definitions, reference: str) -> dict[str, Any]:
    """Render the manifest of `definitions`, which the Lambdas import as `reference` (module:attribute)."""
    states: dict[str, Any] = {
        "plan": {
            **_invoke(PLAN, {"config.$": "$", "run_id.$": "$$.Execution.Name", "started_at.$": "$$.Execution.StartTime"}),
            "Retry": _retries(0),
        }
    }
    # State names are limited to 80 characters; the level number keeps truncated ones unique.
    names = [f"level {i}: {', '.join(level)}"[:80] for i, level in enumerate(definitions.levels, start=1)]
    states["plan"]["Next"] = names[0]
    for i, (name, level) in enumerate(zip(names, definitions.levels, strict=True)):
        if len(level) == 1:
            state = _task(definitions[level[0]])
        else:
            state = {
                "Type": "Parallel",
                "Branches": [{"StartAt": n, "States": {n: {**_task(definitions[n]), "End": True}}} for n in level],
            }
        if i + 1 < len(names):
            state["Next"] = names[i + 1]
        else:
            state["End"] = True
        states[name] = state

    functions: dict[str, Any] = {
        PLAN: _function("stepdag.aws.plan_handler", 256, 60, 512, "default", {"STEPDAG_DEFINITIONS": reference})
    }
    for a in definitions.assets:
        functions[a.name] = _function(
            "stepdag.aws.asset_handler",
            a.memory,
            a.timeout,
            a.ephemeral_storage,
            a.role,
            {"STEPDAG_DEFINITIONS": reference, "STEPDAG_ASSET": a.name},
        )

    return {
        "version": 1,
        "definitions": reference,
        "roles": sorted({f["role"] for f in functions.values()}),
        "functions": functions,
        "state_machine": {
            "Comment": f"stepdag graph {reference}",
            "StartAt": "plan",
            "States": states,
        },
    }


def _invoke(function: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    parameters: dict[str, Any] = {"FunctionName": f"{PREFIX}{function}"}
    if payload is None:
        parameters["Payload.$"] = "$"
    else:
        parameters["Payload"] = payload
    return {"Type": "Task", "Resource": "arn:aws:states:::lambda:invoke", "Parameters": parameters, "OutputPath": "$.Payload"}


def _task(a: Asset) -> dict[str, Any]:
    return {**_invoke(a.name), "Retry": _retries(a.retry_attempts)}


def _retries(own_error_attempts: int) -> list[dict[str, Any]]:
    retries: list[dict[str, Any]] = [{"ErrorEquals": TRANSIENT_ERRORS, "IntervalSeconds": 2, "MaxAttempts": 2, "BackoffRate": 2.0}]
    if own_error_attempts:
        # Retriers match in order: stepdag's own failures are deterministic, so they stop here.
        retries.append({"ErrorEquals": STEPDAG_ERRORS, "MaxAttempts": 0})
        retries.append({"ErrorEquals": ["States.TaskFailed"], "IntervalSeconds": 5, "MaxAttempts": own_error_attempts, "BackoffRate": 2.0})
    return retries


def _function(handler: str, memory: int, timeout: int, storage: int, role: str, environment: dict[str, str]) -> dict[str, Any]:
    return {
        "handler": handler,
        "memory": memory,
        "timeout": timeout,
        "ephemeral_storage": storage,
        "role": role,
        "environment": environment,
    }

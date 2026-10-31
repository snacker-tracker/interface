"""The manifest's seam: what Terraform reads to create the Lambdas and the state machine."""

from typing import Any

from stepdag import Definitions, asset
from stepdag.manifest import render

TRANSIENT = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"]


def diamond() -> Definitions:
    @asset(io_manager="m")
    def root() -> int:
        return 1

    @asset(deps=["root"], io_manager="m", memory=1024, timeout=300, ephemeral_storage=2048, role="big")
    def left(n: int) -> int:
        return n

    @asset(deps=["root"], io_manager="m", retry_attempts=3)
    def right(n: int) -> int:
        return n

    @asset(deps=["left", "right"], io_manager="m")
    def tip(a: int, b: int) -> int:
        return a + b

    return Definitions([tip, right, left, root])


def states(manifest: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = manifest["state_machine"]["States"]
    return result


def test_the_plan_runs_first_then_each_level_in_order() -> None:
    manifest = render(diamond(), "graph:defs")
    machine = manifest["state_machine"]

    assert machine["StartAt"] == "plan"
    assert states(manifest)["plan"]["Next"] == "level 1: root"
    assert states(manifest)["level 1: root"]["Next"] == "level 2: left, right"
    assert states(manifest)["level 2: left, right"]["Next"] == "level 3: tip"
    assert states(manifest)["level 3: tip"]["End"] is True


def test_assets_of_one_level_run_as_parallel_branches() -> None:
    level = states(render(diamond(), "graph:defs"))["level 2: left, right"]

    assert level["Type"] == "Parallel"
    assert [b["StartAt"] for b in level["Branches"]] == ["left", "right"]


def test_each_task_invokes_its_function_with_the_whole_state() -> None:
    task = states(render(diamond(), "graph:defs"))["level 1: root"]

    assert task["Type"] == "Task"
    assert task["Resource"] == "arn:aws:states:::lambda:invoke"
    assert task["Parameters"] == {"FunctionName": "${function_prefix}root", "Payload.$": "$"}
    assert task["OutputPath"] == "$.Payload"


def test_the_plan_gets_the_execution_input_as_run_config_and_the_execution_name_as_run_id() -> None:
    plan = states(render(diamond(), "graph:defs"))["plan"]

    assert plan["Parameters"] == {
        "FunctionName": "${function_prefix}_plan",
        "Payload": {"config.$": "$", "run_id.$": "$$.Execution.Name", "started_at.$": "$$.Execution.StartTime"},
    }


def test_transient_lambda_errors_are_retried_and_stepdags_own_failures_never_are() -> None:
    root = states(render(diamond(), "graph:defs"))["level 1: root"]

    assert root["Retry"] == [{"ErrorEquals": TRANSIENT, "IntervalSeconds": 2, "MaxAttempts": 2, "BackoffRate": 2.0}]


def test_an_asset_can_opt_into_retrying_its_own_errors() -> None:
    level = states(render(diamond(), "graph:defs"))["level 2: left, right"]
    right = level["Branches"][1]["States"]["right"]

    assert right["Retry"][1:] == [
        {"ErrorEquals": ["CheckFailed", "PlanFailed", "StepFailed"], "MaxAttempts": 0},
        {"ErrorEquals": ["States.TaskFailed"], "IntervalSeconds": 5, "MaxAttempts": 3, "BackoffRate": 2.0},
    ]


def test_functions_carry_their_sizes_role_handler_and_environment() -> None:
    functions = render(diamond(), "graph:defs")["functions"]

    assert set(functions) == {"_plan", "root", "left", "right", "tip"}
    assert functions["left"] == {
        "handler": "stepdag.aws.asset_handler",
        "memory": 1024,
        "timeout": 300,
        "ephemeral_storage": 2048,
        "role": "big",
        "environment": {"STEPDAG_DEFINITIONS": "graph:defs", "STEPDAG_ASSET": "left"},
    }
    assert functions["_plan"]["handler"] == "stepdag.aws.plan_handler"
    assert functions["_plan"]["environment"] == {"STEPDAG_DEFINITIONS": "graph:defs"}


def test_the_roles_are_listed_for_terraform_to_map() -> None:
    assert render(diamond(), "graph:defs")["roles"] == ["big", "default"]

"""`stepdag report`: a finished execution's history, turned into the run file a page draws."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "hello"))

from hello import defs  # noqa: E402

from stepdag.report import report  # noqa: E402

RUN = "run-2"
EARLIER = "run-1"
SELECTED = ["greeting", "counter", "shout", "word_count", "report"]


def pointer(asset: str, run_id: str, **metadata: Any) -> dict[str, Any]:
    return {"asset": asset, "io_manager": "run_json", "uri": f"s3://private/{asset}.json", "metadata": {"run_id": run_id, **metadata}}


class History:
    """Execution history events, in the shape GetExecutionHistory returns, built step by step."""

    def __init__(self, selected: list[str] = SELECTED, config: dict[str, Any] | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self.run = {"run_id": RUN, "started_at": "2026-10-31T11:09:04.803Z", "config": config or {}, "selected": selected}
        self.pointers: dict[str, Any] = {}
        self.add("ExecutionStarted", "11:09:04")
        self.step("plan", "11:09:05", "11:09:06")

    def add(self, kind: str, at: str, previous: int | None = None, **details: Any) -> int:
        """Add an event, caused by event `previous` (the one before it by default); returns its id."""
        id = len(self.events) + 1
        self.events.append({
            "id": id,
            "previousEventId": previous if previous is not None else id - 1,
            "type": kind,
            "timestamp": f"2026-10-31T{at}.000000+00:00",
            **details,
        })
        return id

    def step(self, state: str, entered: str, exited: str, pointer: dict[str, Any] | None = None) -> None:
        self.add("TaskStateEntered", entered, stateEnteredEventDetails={"name": state})
        if pointer is not None:
            self.pointers = {**self.pointers, pointer["asset"]: pointer}
        output = {"run": self.run, "pointers": self.pointers}
        self.add("TaskStateExited", exited, stateExitedEventDetails={"name": state, "output": json.dumps(output)})

    def enters(self, state: str, at: str) -> int:
        return self.add("TaskStateEntered", at, stateEnteredEventDetails={"name": state})

    def fails(self, entered_event: int, at: str, error: str, cause: str) -> None:
        """The task of the state entered at `entered_event` fails, and so the execution does."""
        scheduled = self.add("TaskScheduled", at, previous=entered_event)
        self.add("TaskFailed", at, previous=scheduled, taskFailedEventDetails={"error": error, "cause": cause})
        self.add("ExecutionFailed", at, executionFailedEventDetails={"error": error, "cause": cause})


def execution(status: str = "SUCCEEDED", stopped: str = "11:09:30", name: str = RUN, input: str = "{}") -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "startDate": "2026-10-31T11:09:04.803000+00:00",
        "stopDate": f"2026-10-31T{stopped}.000000+00:00",
        "input": input,
    }


def a_whole_run() -> History:
    history = History()
    history.step("greeting", "11:09:06", "11:09:08", pointer("greeting", RUN))
    history.step("counter", "11:09:06", "11:09:07", pointer("counter", EARLIER))
    history.step("shout", "11:09:08", "11:09:10", pointer("shout", RUN))
    history.step("word_count", "11:09:08", "11:09:09", pointer("word_count", RUN))
    history.step("level 3: report", "11:09:10", "11:09:13", pointer("report", RUN, version=7))
    history.add("ExecutionSucceeded", "11:09:30")
    return history


def test_a_finished_run_records_its_outcome_trigger_and_graph() -> None:
    result = report(defs, "hello:defs", execution(), a_whole_run().events)

    assert result["graph"] == "hello:defs"
    assert result["run"] == {
        "id": RUN,
        "status": "SUCCEEDED",
        "started_at": "2026-10-31T11:09:04.803000+00:00",
        "stopped_at": "2026-10-31T11:09:30.000000+00:00",
        "config": {},
        "error": None,
    }
    assert result["levels"] == [["counter", "greeting"], ["shout", "word_count"], ["report"]]


def test_each_asset_has_its_parents_level_status_times_and_version() -> None:
    assets = {a["name"]: a for a in report(defs, "hello:defs", execution(), a_whole_run().events)["assets"]}

    assert assets["report"] == {
        "name": "report",
        "level": 2,
        "deps": ["shout", "word_count", "counter"],
        "io_manager": "run_json",
        "status": "computed",
        "started_at": "2026-10-31T11:09:10.000000+00:00",
        "stopped_at": "2026-10-31T11:09:13.000000+00:00",
        "version": 7,
        "written_by": RUN,
    }
    # counter re-emitted an earlier run's pointer: it skipped.
    assert assets["counter"]["status"] == "skipped"
    assert assets["counter"]["written_by"] == EARLIER
    assert assets["greeting"]["version"] is None


def test_no_uri_is_published() -> None:
    result = report(defs, "hello:defs", execution(), a_whole_run().events)

    assert "s3://" not in json.dumps(result)


def test_a_failed_run_names_the_failing_step_and_what_never_ran() -> None:
    history = History()
    history.step("greeting", "11:09:06", "11:09:08", pointer("greeting", RUN))
    history.step("counter", "11:09:06", "11:09:07", pointer("counter", RUN))
    history.step("shout", "11:09:08", "11:09:10", pointer("shout", RUN))
    history.fails(history.enters("word_count", "11:09:08"), "11:09:11", "StepFailed", "word_count: boom")

    result = report(defs, "hello:defs", execution(status="FAILED", stopped="11:09:11"), history.events)

    assert result["run"]["error"] == {"step": "word_count", "error": "StepFailed", "cause": "word_count: boom"}
    statuses = {a["name"]: a["status"] for a in result["assets"]}
    assert statuses == {
        "counter": "computed",
        "greeting": "computed",
        "shout": "computed",
        "word_count": "failed",
        "report": "not_run",
    }


def test_assets_outside_the_selection_are_marked_so() -> None:
    history = History(selected=["shout"], config={"select": ["shout"]})
    history.step("greeting", "11:09:06", "11:09:07", pointer("greeting", EARLIER))
    history.step("counter", "11:09:06", "11:09:07", pointer("counter", EARLIER))
    history.step("shout", "11:09:07", "11:09:09", pointer("shout", RUN))
    history.step("word_count", "11:09:07", "11:09:08", pointer("word_count", EARLIER))
    history.step("level 3: report", "11:09:09", "11:09:10", pointer("report", EARLIER))
    history.add("ExecutionSucceeded", "11:09:12")

    result = report(defs, "hello:defs", execution(input='{"select": ["shout"]}'), history.events)

    statuses = {a["name"]: a["status"] for a in result["assets"]}
    assert statuses == {"counter": "not_selected", "greeting": "not_selected", "shout": "computed", "word_count": "not_selected", "report": "not_selected"}
    assert result["run"]["config"] == {"select": ["shout"]}


def test_a_failure_is_traced_to_its_own_branch_when_branches_interleave() -> None:
    history = History()
    greeting = history.enters("greeting", "11:09:06")
    history.step("counter", "11:09:06", "11:09:07", pointer("counter", RUN))  # entered after greeting
    history.fails(greeting, "11:09:08", "StepFailed", "greeting: boom")

    result = report(defs, "hello:defs", execution(status="FAILED", stopped="11:09:08"), history.events)

    assert result["run"]["error"]["step"] == "greeting"
    statuses = {a["name"]: a["status"] for a in result["assets"]}
    assert (statuses["greeting"], statuses["counter"]) == ("failed", "computed")

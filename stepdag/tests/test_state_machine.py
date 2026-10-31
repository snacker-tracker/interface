"""The hello graph's manifest, run by an ASL interpreter that calls the real Lambda handlers against a fake S3."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from stepdag import aws
from stepdag.manifest import render
from tests.asl import ExecutionFailed, execute
from tests.fakes import s3_bucket

HELLO = Path(__file__).parent.parent / "examples" / "hello"
BUCKET = "hello-values"
s3: Any = None


@pytest.fixture
def manifest(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """The hello graph's manifest, with its "lambda" bindings pointed at a fake bucket."""
    global s3
    monkeypatch.syspath_prepend(str(HELLO))
    monkeypatch.setenv("STEPDAG_BUCKET", BUCKET)
    with s3_bucket(BUCKET) as client:
        s3 = client
        aws._loaded.cache_clear()  # Each test is a fresh set of cold starts against a fresh bucket.
        import hello

        yield render(hello.defs, "hello:defs")


def stored(key: str) -> Any:
    try:
        body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None
    return json.loads(body)["value"]


def test_one_execution_materializes_all_six_assets(manifest: dict[str, Any]) -> None:
    output = execute(manifest, {}, "first")

    assert stored("fixed/counter.json") == 1
    assert stored("runs/first/report.json") == {"shout": "HELLO, WORLD!", "words": 2, "count": 1}
    assert stored("runs/first/shout.json") == "HELLO, WORLD!"
    assert output["pointers"]["report"]["uri"] == "s3://hello-values/runs/first/report.json"


def test_a_second_execution_skips_greeting_and_counts_up(manifest: dict[str, Any]) -> None:
    execute(manifest, {}, "first")
    output = execute(manifest, {}, "second")

    assert stored("runs/second/report.json")["count"] == 2
    assert output["pointers"]["greeting"]["metadata"]["run_id"] == "first"


def test_fail_check_fails_at_report_and_stores_nothing_for_it(manifest: dict[str, Any]) -> None:
    execute(manifest, {}, "first")

    with pytest.raises(ExecutionFailed) as failure:
        execute(manifest, {"fail_check": True}, "failing")

    assert failure.value.state == "level 3: report"
    assert failure.value.error == "CheckFailed"
    assert stored("runs/failing/report.json") is None
    assert stored("runs/failing/shout.json") == "HELLO, WORLD!"


def test_force_resets_the_counter(manifest: dict[str, Any]) -> None:
    execute(manifest, {}, "first")
    execute(manifest, {}, "second")

    execute(manifest, {"force": True}, "forced")

    assert stored("runs/forced/report.json")["count"] == 1


def test_a_selection_is_planned_before_anything_runs(manifest: dict[str, Any]) -> None:
    with pytest.raises(ExecutionFailed) as failure:
        execute(manifest, {"select": ["report"]}, "too-soon")

    assert failure.value.state == "plan"
    assert failure.value.error == "PlanFailed"
    assert stored("fixed/counter.json") is None


def test_a_selection_runs_only_what_it_names(manifest: dict[str, Any]) -> None:
    execute(manifest, {}, "first")

    output = execute(manifest, {"select": ["counter"], "downstream": True, "name": "Ada"}, "partial")

    assert stored("runs/partial/report.json") == {"shout": "HELLO, WORLD!", "words": 2, "count": 2}
    assert stored("runs/partial/shout.json") is None
    assert output["pointers"]["shout"]["metadata"]["run_id"] == "first"

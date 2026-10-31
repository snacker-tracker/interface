"""Smoke tests of the CLI, on the hello graph with its local-directory binding."""

import json
from pathlib import Path

import pytest

from stepdag.cli import main

HELLO = Path(__file__).parent.parent / "examples" / "hello"


@pytest.fixture
def hello(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.chdir(HELLO)
    monkeypatch.setenv("STEPDAG_DIR", str(tmp_path))
    return tmp_path


def report(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = json.loads(capsys.readouterr().out)
    value: dict[str, object] = out["values"]["report"]
    return value


def test_stepdag_run_runs_the_hello_graph_into_a_local_directory(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "hello:defs"]) == 0

    assert report(capsys)["shout"] == "HELLO, WORLD!"
    assert list(hello.glob("runs/*/report.json"))


def test_stepdag_run_takes_run_config(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "hello:defs", "--config", '{"name": "Ada"}']) == 0

    value = report(capsys)
    assert value["shout"] == "HELLO, ADA!"
    assert value["words"] == 2


def test_a_second_run_counts_up_and_skips_an_unchanged_greeting(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "hello:defs"])
    capsys.readouterr()

    assert main(["run", "hello:defs"]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["values"]["report"]["count"] == 2
    assert out["skipped"] == ["greeting"]


def test_select_downstream_and_force_flags(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "hello:defs"])
    main(["run", "hello:defs"])
    capsys.readouterr()

    assert main(["run", "hello:defs", "--select", "counter", "--downstream", "--force"]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["computed"] == ["counter", "report"]
    assert out["values"]["report"]["count"] == 1


def test_fail_check_fails_report_and_stores_nothing_for_it(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "hello:defs"])
    before = sorted(hello.glob("runs/*/report.json"))

    assert main(["run", "hello:defs", "--config", '{"fail_check": true}']) == 1

    assert "CheckFailed: report failed its checks: counted" in capsys.readouterr().err
    assert sorted(hello.glob("runs/*/report.json")) == before


def test_stepdag_manifest_prints_the_manifest(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["manifest", "hello:defs"]) == 0

    manifest = json.loads(capsys.readouterr().out)
    assert set(manifest["functions"]) == {"_plan", "greeting", "counter", "shout", "word_count", "report"}


def test_the_committed_hello_manifest_is_up_to_date(hello: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["manifest", "hello:defs"])

    committed = (HELLO / "infra" / "manifest.json").read_text()
    assert json.loads(capsys.readouterr().out) == json.loads(committed), "run: stepdag manifest hello:defs > infra/manifest.json"


def test_values_that_arent_json_are_shown_by_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "opaque.py").write_text(
        "from stepdag import Definitions, Pointer, asset\n"
        "class Box:\n"
        "    def __init__(self): self.values = {}\n"
        "    def store(self, value, asset, context):\n"
        "        self.values[asset] = value\n"
        "        return Pointer(asset, 'box', f'box://{asset}')\n"
        "    def load(self, pointer): return self.values[pointer.asset]\n"
        "    def latest(self, asset, partition=None): return None\n"
        "@asset(io_manager='box')\n"
        "def thing(): return object()\n"
        "defs = Definitions([thing], environments={'local': lambda: {'box': Box()}})\n"
    )
    monkeypatch.chdir(tmp_path)

    assert main(["run", "opaque:defs"]) == 0

    assert json.loads(capsys.readouterr().out)["values"] == {"thing": "<object>"}

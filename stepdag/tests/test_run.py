"""The local executor's seam: run a graph, then read the results back through its IO managers."""

from typing import Any

import pytest

from stepdag import UNCHANGED, Definitions, DefinitionError, RunContext, asset, run
from stepdag.json_io import MemoryStore, RunJson


def value_of(io_managers: dict[str, Any], result: Any, name: str) -> Any:
    pointer = result.pointers[name]
    return io_managers[pointer.io_manager].load(pointer)


def run_json() -> dict[str, Any]:
    return {"run_json": RunJson(MemoryStore())}


def test_parents_reach_a_function_positionally_in_deps_order() -> None:
    @asset(io_manager="run_json")
    def a() -> int:
        return 2

    @asset(io_manager="run_json")
    def b() -> int:
        return 10

    @asset(deps=["b", "a"], io_manager="run_json")
    def c(first: int, second: int) -> int:
        return first - second

    io = run_json()
    result = run(Definitions([c, a, b]), io)

    assert value_of(io, result, "c") == 8


def test_fan_out_and_fan_in() -> None:
    @asset(io_manager="run_json")
    def root() -> str:
        return "a b c"

    @asset(deps=["root"], io_manager="run_json")
    def upper(text: str) -> str:
        return text.upper()

    @asset(deps=["root"], io_manager="run_json")
    def words(text: str) -> int:
        return len(text.split())

    @asset(deps=["upper", "words"], io_manager="run_json")
    def summary(text: str, count: int) -> str:
        return f"{text}/{count}"

    io = run_json()
    result = run(Definitions([summary, words, upper, root]), io)

    assert value_of(io, result, "summary") == "A B C/3"
    assert set(result.computed) == {"root", "upper", "words", "summary"}


def test_shared_run_config_and_asset_sections_reach_the_context() -> None:
    seen: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    @asset(io_manager="run_json")
    def a(*, context: RunContext) -> None:
        seen["a"] = (context.config, context.asset_config)

    @asset(io_manager="run_json")
    def b(*, context: RunContext) -> None:
        seen["b"] = (context.config, context.asset_config)

    run(Definitions([a, b]), run_json(), config={"name": "Ada", "a": {"loud": True}})

    assert seen["a"] == ({"name": "Ada"}, {"loud": True})
    assert seen["b"] == ({"name": "Ada"}, {})


def test_the_context_carries_the_run_id_shared_by_every_asset() -> None:
    ids: list[str] = []

    @asset(io_manager="run_json")
    def a(*, context: RunContext) -> None:
        ids.append(context.run_id)

    @asset(deps=["a"], io_manager="run_json")
    def b(_: None, *, context: RunContext) -> None:
        ids.append(context.run_id)

    result = run(Definitions([a, b]), run_json())

    assert ids == [result.run_id, result.run_id]


def test_a_function_taking_the_wrong_number_of_parents_is_rejected() -> None:
    with pytest.raises(DefinitionError, match="2 deps"):

        @asset(deps=["x", "y"], io_manager="run_json")
        def a(x: int) -> int:
            return x


def test_an_unknown_parent_is_rejected() -> None:
    @asset(deps=["missing"], io_manager="run_json")
    def a(x: int) -> int:
        return x

    with pytest.raises(DefinitionError, match="missing"):
        Definitions([a])


def test_a_cycle_is_rejected() -> None:
    @asset(deps=["b"], io_manager="run_json")
    def a(x: int) -> int:
        return x

    @asset(deps=["a"], io_manager="run_json")
    def b(x: int) -> int:
        return x

    with pytest.raises(DefinitionError, match="cycle"):
        Definitions([a, b])


def fixed_and_run_json() -> dict[str, Any]:
    from stepdag.json_io import FixedJson

    store = MemoryStore()
    return {"run_json": RunJson(store), "fixed_json": FixedJson(store)}


def test_previous_is_none_at_first_then_the_latest_materialization() -> None:
    @asset(io_manager="fixed_json")
    def counter(*, previous: int | None) -> int:
        return (previous or 0) + 1

    io = fixed_and_run_json()
    defs = Definitions([counter])

    assert value_of(io, run(defs, io), "counter") == 1
    assert value_of(io, run(defs, io), "counter") == 2
    assert value_of(io, run(defs, io), "counter") == 3


def test_unchanged_re_emits_the_latest_pointer_to_the_assets_after_it() -> None:
    from stepdag import UNCHANGED

    @asset(io_manager="fixed_json")
    def text(*, previous: str | None, context: RunContext) -> str:
        new = f"Hello, {context.config.get('name', 'world')}!"
        return UNCHANGED if new == previous else new

    @asset(deps=["text"], io_manager="run_json")
    def upper(t: str) -> str:
        return t.upper()

    io = fixed_and_run_json()
    defs = Definitions([text, upper])
    first = run(defs, io)
    second = run(defs, io)

    assert second.computed == []
    assert second.skipped == ["text", "upper"]
    assert second.pointers["text"] == first.pointers["text"]
    assert value_of(io, second, "upper") == "HELLO, WORLD!"  # Read before a later run retains only its own.

    third = run(defs, io, config={"name": "Ada"})

    assert third.computed == ["text", "upper"]
    assert value_of(io, third, "upper") == "HELLO, ADA!"


def test_unchanged_with_nothing_to_re_emit_fails_the_run() -> None:
    from stepdag import UNCHANGED, StepFailed

    @asset(io_manager="fixed_json")
    def lazy() -> Any:
        return UNCHANGED

    with pytest.raises(StepFailed, match="lazy.*no materialization"):
        run(Definitions([lazy]), fixed_and_run_json())


def three_in_a_row() -> Definitions:
    @asset(io_manager="fixed_json")
    def first(*, previous: int | None) -> int:
        return (previous or 0) + 1

    @asset(deps=["first"], io_manager="run_json")
    def second(n: int) -> int:
        return n * 10

    @asset(deps=["second"], io_manager="run_json")
    def third(n: int) -> int:
        return n + 1

    @asset(io_manager="fixed_json")
    def other(*, previous: int | None) -> int:
        return (previous or 0) + 1

    return Definitions([first, second, third, other])


def test_a_selection_materializes_only_the_named_assets() -> None:
    io = fixed_and_run_json()
    defs = three_in_a_row()
    full = run(defs, io)

    result = run(defs, io, select=["third"])

    # Third is selected, but its parent is unchanged since its last run, so it skips too.
    assert result.computed == []
    assert result.skipped == ["first", "other", "second", "third"]
    assert result.pointers["second"] == full.pointers["second"]
    assert value_of(io, result, "first") == 1


def test_a_selected_asset_whose_parent_changed_computes_while_an_unselected_one_re_emits() -> None:
    io = fixed_and_run_json()
    defs = three_in_a_row()
    run(defs, io)

    result = run(defs, io, select=["first"], downstream=True)

    assert result.computed == ["first", "second", "third"]
    assert result.skipped == ["other"]
    assert value_of(io, result, "other") == 1


def test_downstream_adds_everything_after_the_selection() -> None:
    io = fixed_and_run_json()
    defs = three_in_a_row()
    run(defs, io)

    result = run(defs, io, select=["first"], downstream=True)

    assert result.computed == ["first", "second", "third"]
    assert value_of(io, result, "third") == 21
    assert value_of(io, result, "other") == 1


def test_an_unselected_asset_with_no_materialization_fails_before_anything_runs() -> None:
    from stepdag import PlanFailed

    io = fixed_and_run_json()
    defs = three_in_a_row()

    with pytest.raises(PlanFailed, match="first, other, second"):
        run(defs, io, select=["third"])

    assert io["fixed_json"].latest("first") is None


def test_selecting_an_unknown_asset_fails_the_run() -> None:
    from stepdag import PlanFailed

    with pytest.raises(PlanFailed, match="nope"):
        run(three_in_a_row(), fixed_and_run_json(), select=["nope"])


def test_a_forced_run_gives_no_previous_and_skips_nothing() -> None:
    from stepdag import UNCHANGED

    @asset(io_manager="fixed_json")
    def same(*, previous: str | None) -> str:
        return UNCHANGED if previous == "x" else "x"

    @asset(io_manager="fixed_json")
    def counter(*, previous: int | None) -> int:
        return (previous or 0) + 1

    io = fixed_and_run_json()
    defs = Definitions([same, counter])
    run(defs, io)
    run(defs, io)

    result = run(defs, io, force=True)

    assert result.computed == ["counter", "same"]
    assert value_of(io, result, "counter") == 1


def test_force_in_the_run_config_forces_too() -> None:
    @asset(io_manager="fixed_json")
    def counter(*, previous: int | None) -> int:
        return (previous or 0) + 1

    io = fixed_and_run_json()
    defs = Definitions([counter])
    run(defs, io)

    assert value_of(io, run(defs, io, config={"force": True}), "counter") == 1


def test_force_with_a_selection_forces_only_the_selected_assets() -> None:
    io = fixed_and_run_json()
    defs = three_in_a_row()
    run(defs, io)
    run(defs, io)

    result = run(defs, io, select=["other"], force=True)

    assert value_of(io, result, "other") == 1
    assert value_of(io, result, "first") == 2


def test_a_forced_function_returning_unchanged_fails_the_run() -> None:
    from stepdag import UNCHANGED, StepFailed

    @asset(io_manager="fixed_json")
    def stubborn() -> Any:
        return UNCHANGED

    @asset(io_manager="fixed_json")
    def seed() -> int:
        return 1

    io = fixed_and_run_json()
    io["fixed_json"].store("old", "stubborn", RunContext("r0", "", "stubborn", {}, {}, False))

    with pytest.raises(StepFailed, match="stubborn.*forced"):
        run(Definitions([stubborn, seed]), io, force=True)


def test_a_failed_check_fails_the_run_and_stores_nothing() -> None:
    from stepdag import CheckFailed

    def positive(value: int, context: RunContext) -> str | None:
        return None if value > 0 else f"{value} isn't positive"

    @asset(io_manager="fixed_json", checks=[positive])
    def number(*, context: RunContext) -> int:
        return int(context.config.get("n", 1))

    io = fixed_and_run_json()
    defs = Definitions([number])
    good = run(defs, io)

    with pytest.raises(CheckFailed, match="number.*positive: -3 isn't positive"):
        run(defs, io, config={"n": -3})

    assert io["fixed_json"].latest("number") == good.pointers["number"]


def test_every_failing_check_is_reported() -> None:
    from stepdag import CheckFailed

    def never(value: int, context: RunContext) -> str | None:
        return "never passes"

    def always(value: int, context: RunContext) -> str | None:
        return None

    def also_never(value: int, context: RunContext) -> str | None:
        return "nor this"

    @asset(io_manager="run_json", checks=[never, always, also_never])
    def a() -> int:
        return 1

    with pytest.raises(CheckFailed) as failure:
        run(Definitions([a]), fixed_and_run_json())

    assert failure.value.failures == {"never": "never passes", "also_never": "nor this"}


def test_checks_see_the_run_context_and_passing_ones_change_nothing() -> None:
    def not_asked_to_fail(value: int, context: RunContext) -> str | None:
        return "asked to fail" if context.asset_config.get("fail") else None

    @asset(io_manager="run_json", checks=[not_asked_to_fail])
    def a() -> int:
        return 7

    io = fixed_and_run_json()
    result = run(Definitions([a]), io)

    assert value_of(io, result, "a") == 7


def test_a_run_can_be_given_its_start_time() -> None:
    from datetime import UTC, datetime

    seen: list[str] = []

    @asset(io_manager="run_json")
    def a(*, context: RunContext) -> None:
        seen.append(context.started_at)

    result = run(Definitions([a]), run_json(), started_at=datetime(2026, 10, 19, 12, 0, tzinfo=UTC))

    assert seen == ["2026-10-19T12:00:00+00:00"]
    assert result.run_id.startswith("local-20261019T120000-")


class AskedForLatest(RunJson):
    """`run_json`, recording each asset `latest()` is asked about."""

    def __init__(self) -> None:
        super().__init__(MemoryStore())
        self.asked: list[str] = []

    def latest(self, asset: str, partition: str | None = None) -> Any:
        self.asked.append(asset)
        return super().latest(asset, partition)


def test_an_asset_with_parents_asks_for_its_latest_only_when_it_may_skip() -> None:
    @asset(io_manager="run_json")
    def a() -> int:
        return 1

    @asset(deps=["a"], io_manager="run_json", skip_when_unchanged=False)
    def opted_out(n: int) -> int:
        return n + 1

    @asset(deps=["a"], io_manager="run_json")
    def child(n: int) -> int:
        return n + 1

    io = AskedForLatest()
    defs = Definitions([a, opted_out, child])
    run(defs, {"run_json": io})
    io.asked.clear()

    run(defs, {"run_json": io})
    assert "opted_out" not in io.asked
    assert "child" in io.asked

    io.asked.clear()
    run(defs, {"run_json": io}, force=True)
    assert io.asked == []


def test_a_root_that_takes_no_previous_and_returns_a_value_never_asks_for_its_latest() -> None:
    @asset(io_manager="run_json")
    def a() -> int:
        return 1

    io = AskedForLatest()
    defs = Definitions([a])
    run(defs, {"run_json": io})
    run(defs, {"run_json": io})

    assert io.asked == []


def test_an_asset_without_previous_that_returns_unchanged_re_emits_its_latest() -> None:
    from stepdag import UNCHANGED

    @asset(io_manager="run_json")
    def a(*, context: RunContext) -> Any:
        return UNCHANGED if context.config.get("skip") else 1

    io = run_json()
    defs = Definitions([a])
    first = run(defs, io)

    second = run(defs, io, config={"skip": True})

    assert second.skipped == ["a"]
    assert second.pointers["a"] == first.pointers["a"]


def steady_and_changing(calls: list[str]) -> Definitions:
    """`changing` takes the run config's `value`, and is UNCHANGED while it stays the same. `steady` is UNCHANGED after its first run."""

    @asset(io_manager="fixed_json")
    def changing(*, previous: int | None, context: RunContext) -> Any:
        value = int(context.config.get("value", 0))
        return UNCHANGED if value == previous else value

    @asset(io_manager="fixed_json")
    def steady(*, previous: str | None) -> Any:
        return UNCHANGED if previous is not None else "fixed"

    @asset(deps=["changing"], io_manager="run_json")
    def after_changing(value: int, *, context: RunContext) -> int:
        calls.append("after_changing")
        if context.config.get("fail"):
            raise RuntimeError("asked to fail")
        return value * 10

    @asset(deps=["steady"], io_manager="run_json")
    def after_steady(value: str) -> str:
        calls.append("after_steady")
        return value + "!"

    return Definitions([changing, steady, after_changing, after_steady])


def test_a_child_of_an_unchanged_root_skips_while_a_child_of_a_changing_root_computes() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = steady_and_changing(calls)
    run(defs, io, config={"value": 0})

    second = run(defs, io, config={"value": 1})

    assert second.computed == ["changing", "after_changing"]
    assert second.skipped == ["steady", "after_steady"]
    assert calls == ["after_changing", "after_steady", "after_changing"]
    assert value_of(io, second, "after_steady") == "fixed!"
    assert value_of(io, second, "after_changing") == 10


def test_a_child_that_failed_after_its_parent_changed_computes_next_run_though_the_parent_is_unchanged() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = steady_and_changing(calls)
    run(defs, io, config={"value": 0})
    with pytest.raises(RuntimeError):
        run(defs, io, config={"value": 1, "fail": True})

    third = run(defs, io, config={"value": 1})

    assert third.skipped == ["changing", "steady", "after_steady"]
    assert third.computed == ["after_changing"]
    assert value_of(io, third, "after_changing") == 10


def test_a_root_is_computed_every_run_even_when_nothing_could_have_changed() -> None:
    calls: list[str] = []

    @asset(io_manager="run_json")
    def source() -> int:
        calls.append("source")
        return 1

    io = run_json()
    defs = Definitions([source])
    run(defs, io)

    second = run(defs, io)

    assert second.computed == ["source"]
    assert calls == ["source", "source"]


def test_a_child_with_skip_when_unchanged_turned_off_computes_though_its_parents_are_unchanged() -> None:
    calls: list[str] = []

    @asset(io_manager="run_json")
    def source() -> int:
        return 1

    @asset(deps=["source"], io_manager="run_json", skip_when_unchanged=False)
    def child(n: int) -> int:
        calls.append("child")
        return n + 1

    io = run_json()
    defs = Definitions([source, child])
    run(defs, io)

    second = run(defs, io)

    assert second.computed == ["source", "child"]
    assert calls == ["child", "child"]


def test_skip_when_unchanged_is_on_by_default() -> None:
    @asset(deps=["x"], io_manager="run_json")
    def child(x: int) -> int:
        return x

    @asset(io_manager="run_json")
    def x() -> int:
        return 1

    assert Definitions([child, x])["child"].skip_when_unchanged is True


def test_a_forced_run_computes_a_child_whose_parents_are_unchanged() -> None:
    calls: list[str] = []

    @asset(io_manager="run_json")
    def source() -> int:
        return 1

    @asset(deps=["source"], io_manager="run_json")
    def child(n: int) -> int:
        calls.append("child")
        return n + 1

    io = run_json()
    defs = Definitions([source, child])
    run(defs, io)

    result = run(defs, io, force=True)

    assert result.computed == ["source", "child"]
    assert calls == ["child", "child"]


def test_a_materialization_with_no_recorded_parents_computes() -> None:
    @asset(io_manager="run_json")
    def source() -> int:
        return 1

    @asset(deps=["source"], io_manager="run_json")
    def child(n: int) -> int:
        return n + 1

    io = run_json()
    defs = Definitions([source, child])
    run(defs, io)
    # Written as before stamps existed: a latest materialization with no recorded parents.
    io["run_json"].store(99, "child", RunContext("old", "", "child", {}, {}, False))

    result = run(defs, io)

    assert "child" in result.computed
    assert value_of(io, result, "child") == 2


def test_a_stored_materialization_records_its_parents_pointers_without_their_stamps() -> None:
    @asset(io_manager="run_json")
    def source() -> int:
        return 1

    @asset(deps=["source"], io_manager="run_json")
    def child(n: int) -> int:
        return n + 1

    io = run_json()
    first = run(Definitions([source, child]), io)

    recorded = first.pointers["child"].metadata["stamp"]["parents"]["source"]
    assert recorded == {**first.pointers["source"].to_json(), "metadata": {k: v for k, v in first.pointers["source"].metadata.items() if k != "stamp"}}
    assert "stamp" not in recorded["metadata"]


def test_the_skip_reason_says_the_parents_are_unchanged() -> None:
    from stepdag.execution import materialize, plan

    @asset(io_manager="run_json")
    def source() -> int:
        return 1

    @asset(deps=["source"], io_manager="run_json")
    def child(n: int) -> int:
        return n + 1

    io = run_json()
    defs = Definitions([source, child])
    first = run(defs, io)
    the_run = plan(defs, io, {}, "r2", "2026-11-18T00:00:00+00:00")

    outcome = materialize(defs, "child", {"source": first.pointers["source"]}, the_run, io)

    assert not outcome.computed
    assert "parents" in outcome.reason and "unchanged" in outcome.reason


def source_and_child(calls: list[str]) -> Definitions:
    """`source` is UNCHANGED after its first run, so its pointer, and so `child`'s parents, stay the same."""

    @asset(io_manager="fixed_json")
    def source(*, previous: int | None) -> Any:
        return UNCHANGED if previous is not None else 1

    @asset(deps=["source"], io_manager="run_json")
    def child(n: int) -> int:
        calls.append("child")
        return n + 1

    return Definitions([source, child])


def test_a_materialization_records_the_code_version_it_was_made_by() -> None:
    result = run(source_and_child([]), fixed_and_run_json(), code_version=lambda: "v1")

    assert result.pointers["child"].metadata["stamp"]["code"] == "v1"


def test_the_same_code_version_skips_a_child_whose_parents_are_unchanged() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = source_and_child(calls)
    run(defs, io, code_version=lambda: "v1")

    second = run(defs, io, code_version=lambda: "v1")

    assert second.computed == []
    assert second.skipped == ["source", "child"]
    assert calls == ["child"]


def test_a_different_code_version_computes_a_child_whose_parents_are_unchanged() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = source_and_child(calls)
    run(defs, io, code_version=lambda: "v1")

    second = run(defs, io, code_version=lambda: "v2")

    assert second.computed == ["child"]
    assert second.skipped == ["source"]
    assert calls == ["child", "child"]


def test_no_code_version_never_skips() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = source_and_child(calls)
    first = run(defs, io, code_version=lambda: None)

    second = run(defs, io, code_version=lambda: None)

    assert first.pointers["child"].metadata["stamp"]["code"] is None
    assert second.computed == ["child"]
    assert calls == ["child", "child"]


def test_a_latest_stamped_without_a_code_version_computes_though_its_parents_are_unchanged() -> None:
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = source_and_child(calls)
    first = run(defs, io, code_version=lambda: "v1")
    parents = {k: v for k, v in first.pointers["child"].metadata["stamp"].items() if k != "code"}
    io["run_json"].store(99, "child", RunContext("old", "", "child", {}, {}, False, parents))

    second = run(defs, io, code_version=lambda: "v1")

    assert second.computed == ["child"]
    assert value_of(io, second, "child") == 2


def test_the_default_code_version_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Undo the autouse fixture's patch, so run() reads the real code_version() and its environment variable.
    monkeypatch.undo()
    monkeypatch.setenv("STEPDAG_CODE_VERSION", "sha256:digest")
    calls: list[str] = []
    io = fixed_and_run_json()
    defs = source_and_child(calls)

    first = run(defs, io)
    second = run(defs, io)

    assert first.pointers["child"].metadata["stamp"]["code"] == "sha256:digest"
    assert second.skipped == ["source", "child"]
    assert calls == ["child"]

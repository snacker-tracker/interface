"""The local executor's seam: run a graph, then read the results back through its IO managers."""

from typing import Any

import pytest

from stepdag import Definitions, DefinitionError, RunContext, asset, run
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
    third = run(defs, io, config={"name": "Ada"})

    assert second.computed == ["upper"]
    assert second.skipped == ["text"]
    assert second.pointers["text"] == first.pointers["text"]
    assert value_of(io, second, "upper") == "HELLO, WORLD!"
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

    assert result.computed == ["third"]
    assert result.skipped == ["first", "other", "second"]
    assert result.pointers["second"] == full.pointers["second"]
    assert value_of(io, result, "first") == 1


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

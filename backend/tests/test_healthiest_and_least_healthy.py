"""Tests at the Scan summary seam for the healthiest and least healthy products: the products
with a Nutri-Score scanned within each period, ranked by grade, then by scans."""

from datetime import UTC, datetime

from scans_table import scan, scans_table
from snacker.scan_summary import healthiest_and_least_healthy

# Wednesday 21 October 2026, 12:00 in Bangkok (UTC+7).
NOW = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)
BANGKOK = "Asia/Bangkok"


def scans_of(code: str, nutri_score: str | None, times: int, *, day: int = 1) -> list[dict[str, object]]:
    return [
        scan(code, f"2026-10-{day:02}T0{n}:00:00Z", office_time_zone=BANGKOK,
             product_known=nutri_score is not None, product_nutri_score=nutri_score)
        for n in range(times)
    ]


def ranked(*products: list[dict[str, object]], limit: int = 10) -> tuple[list[str], list[str]]:
    lists = healthiest_and_least_healthy(scans_table(*(row for scans in products for row in scans)), limit=limit, now=NOW)
    all_time = lists["all-time"]
    return [row["code"] for row in all_time["healthiest"]], [row["code"] for row in all_time["least_healthy"]]


def test_products_are_ranked_by_grade_then_by_scans() -> None:
    assert ranked(
        scans_of("water", "A", 1),
        scans_of("soda", "B", 5),
        scans_of("tea", "B", 3),
        scans_of("milk", "C", 2),
        scans_of("cake", "D", 1),
        scans_of("chips", "E", 4),
        scans_of("candy", "E", 2),
        limit=2,
    ) == (["water", "soda"], ["chips", "candy"])


def test_a_few_products_are_split_in_halves_with_the_odd_one_going_to_the_healthiest() -> None:
    assert ranked(
        scans_of("water", "A", 1),
        scans_of("soda", "B", 1),
        scans_of("milk", "C", 1),
        scans_of("cake", "D", 1),
        scans_of("chips", "E", 1),
    ) == (["water", "soda", "milk"], ["chips", "cake"])


def test_a_single_product_is_only_among_the_healthiest_even_when_graded_e() -> None:
    assert ranked(scans_of("chips", "E", 3)) == (["chips"], [])


def test_the_least_healthy_are_the_most_scanned_of_the_worst_grade() -> None:
    # More E products than fit: the most scanned of them are listed, not the leftovers.
    assert ranked(
        scans_of("water", "A", 1),
        scans_of("soda", "B", 1),
        *(scans_of(f"chips-{n}", "E", n) for n in range(1, 5)),
        limit=2,
    ) == (["water", "soda"], ["chips-4", "chips-3"])


def test_products_without_a_nutri_score_are_left_out_but_their_scans_count_towards_coverage() -> None:
    lists = healthiest_and_least_healthy(
        scans_table(*scans_of("water", "A", 2), *scans_of("beer", None, 3)), limit=10, now=NOW
    )["all-time"]

    assert [row["code"] for row in lists["healthiest"] + lists["least_healthy"]] == ["water"]
    assert (lists["graded_scans"], lists["scans"]) == (2, 5)


def test_a_period_without_graded_products_has_empty_lists() -> None:
    lists = healthiest_and_least_healthy(
        scans_table(*scans_of("beer", None, 1, day=1)), limit=10, now=NOW
    )

    assert lists["today"] == {"healthiest": [], "least_healthy": [], "graded_scans": 0, "scans": 0}
    assert lists["all-time"] == {"healthiest": [], "least_healthy": [], "graded_scans": 0, "scans": 1}

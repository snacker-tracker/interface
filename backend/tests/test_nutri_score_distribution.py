"""Tests at the Scan summary seam for the Nutri-Score distribution: how many scans within each
period were of products of each Nutri-Score grade."""

from datetime import UTC, datetime

from scans_table import scan, scans_table
from snacker.scan_summary import nutri_score_distribution

# Wednesday 21 October 2026, 12:00 in Bangkok (UTC+7).
NOW = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)
BANGKOK = "Asia/Bangkok"


def scans_of(
    code: str, nutri_score: str | None, times: int, *, day: int = 1, known: bool | None = None
) -> list[dict[str, object]]:
    return [
        scan(code, f"2026-10-{day:02}T0{n}:00:00Z", office_time_zone=BANGKOK,
             product_known=nutri_score is not None if known is None else known, product_nutri_score=nutri_score)
        for n in range(times)
    ]


def test_every_scan_counts_towards_its_products_grade_and_ungraded_scans_only_towards_the_total() -> None:
    distribution = nutri_score_distribution(
        scans_table(
            *scans_of("water", "A", 3),
            *scans_of("tea", "B", 1),
            *scans_of("soda", "B", 2),
            *scans_of("chips", "E", 1),
            *scans_of("beer", None, 2, known=True),  # OpenFoodFacts has it, without a Nutri-Score
            *scans_of("mystery", None, 4),  # an unknown product
        ),
        now=NOW,
    )

    assert distribution["all-time"] == {
        "grades": {"A": 3, "B": 3, "C": 0, "D": 0, "E": 1},
        "graded_scans": 7,
        "scans": 13,
    }


def test_a_period_without_graded_scans_keeps_every_grade_at_zero() -> None:
    distribution = nutri_score_distribution(
        scans_table(*scans_of("water", "A", 2, day=1), *scans_of("beer", None, 1, day=21)), now=NOW
    )

    assert distribution["today"] == {
        "grades": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
        "graded_scans": 0,
        "scans": 1,
    }
    assert distribution["this-month"]["grades"]["A"] == 2

"""Tests at the Scan summary seam for top scans: which codes were scanned most within each period."""

from datetime import UTC, datetime

import pytest

from scans_table import scan, scans_table
from snacker.contract import PERIODS, Period
from snacker.scan_summary import top_scans

# Wednesday 21 October 2026, 12:00 in Bangkok (UTC+7).
NOW = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)
BANGKOK = "Asia/Bangkok"


def top_codes(scans: list[dict[str, object]], period: Period, *, top_limit: int = 10) -> list[str]:
    return [row["code"] for row in top_scans(scans_table(*scans), limit=top_limit, now=NOW)[period]]


def test_codes_are_ranked_by_scans_with_ties_going_to_the_most_recently_scanned() -> None:
    scans = [
        scan("soda", "2026-10-01T01:00:00Z", office_time_zone=BANGKOK),
        scan("soda", "2026-10-02T01:00:00Z", office_time_zone=BANGKOK),
        scan("soda", "2026-10-03T01:00:00Z", office_time_zone=BANGKOK),
        scan("chips", "2026-10-04T01:00:00Z", office_time_zone=BANGKOK),
        scan("chips", "2026-10-05T01:00:00Z", office_time_zone=BANGKOK),
        scan("nuts", "2026-10-03T01:00:00Z", office_time_zone=BANGKOK),
        scan("nuts", "2026-10-06T01:00:00Z", office_time_zone=BANGKOK),
        scan("gum", "2026-10-07T01:00:00Z", office_time_zone=BANGKOK),
    ]

    assert top_codes(scans, "all-time") == ["soda", "nuts", "chips", "gum"]


def test_each_list_is_cut_to_the_limit() -> None:
    scans = [scan(f"code-{n}", f"2026-10-0{n}T01:00:00Z", office_time_zone=BANGKOK) for n in range(1, 6)]

    assert len(top_codes(scans, "all-time", top_limit=3)) == 3


def test_a_row_names_the_product_counts_its_scans_and_gives_its_share_of_the_period() -> None:
    scans = scans_table(
        scan("8851959132012", "2026-10-20T01:00:00Z", office_time_zone=BANGKOK,
             product_name="Coca Cola", product_brands="Coke", product_known=True),
        scan("8851959132012", "2026-10-20T02:00:00Z", office_time_zone=BANGKOK,
             product_name="Coca Cola", product_brands="Coke", product_known=True),
        scan("005", "2026-10-20T03:00:00Z", office_time_zone=BANGKOK),
        scan("8858702410304", "2026-10-20T04:00:00Z", office_time_zone=BANGKOK, product_known=True),
    )

    rows = top_scans(scans, limit=10, now=NOW)["last-7-days"]

    assert rows == [
        {"code": "8851959132012", "name": "Coca Cola", "name_source": "openfoodfacts", "brands": "Coke", "known": True,
         "count": 2, "share": 0.5},
        {"code": "8858702410304", "name": None, "name_source": None, "brands": None, "known": True, "count": 1, "share": 0.25},
        {"code": "005", "name": None, "name_source": None, "brands": None, "known": False, "count": 1, "share": 0.25},
    ]


def test_every_period_is_listed_even_when_it_has_no_scans() -> None:
    by_period = top_scans(scans_table(), limit=10, now=NOW)

    assert tuple(by_period) == PERIODS
    assert all(rows == [] for rows in by_period.values())


@pytest.mark.parametrize(
    ("period", "just_inside", "just_outside"),
    [
        # Bangkok midnight on Wednesday 21 October is 17:00 UTC on the 20th.
        ("today", "2026-10-20T17:00:00Z", "2026-10-20T16:59:59Z"),
        # The work week starts Monday 19 October, 00:00 Bangkok = 17:00 UTC Sunday.
        ("this-work-week", "2026-10-18T17:00:00Z", "2026-10-18T16:59:59Z"),
        # 1 October 00:00 Bangkok = 17:00 UTC on 30 September.
        ("this-month", "2026-09-30T17:00:00Z", "2026-09-30T16:59:59Z"),
        # 1 January 2026 00:00 Bangkok = 17:00 UTC on 31 December 2025.
        ("this-year", "2025-12-31T17:00:00Z", "2025-12-31T16:59:59Z"),
        # Rolling periods count back exact durations from the build, the cutoff included.
        ("last-7-days", "2026-10-14T05:00:00Z", "2026-10-14T04:59:59Z"),
        ("last-30-days", "2026-09-21T05:00:00Z", "2026-09-21T04:59:59Z"),
        ("last-365-days", "2025-10-21T05:00:00Z", "2025-10-21T04:59:59Z"),
    ],
)
def test_a_period_includes_scans_from_its_start_onwards(period: Period, just_inside: str, just_outside: str) -> None:
    scans = [
        scan("inside", just_inside, office_time_zone=BANGKOK),
        scan("outside", just_outside, office_time_zone=BANGKOK),
    ]

    assert top_codes(scans, period) == ["inside"]


def test_calendar_periods_start_in_each_scans_own_office_time_zone() -> None:
    # 18:00 UTC on the 20th is already the 21st in Bangkok but still the 20th in London.
    scans = [
        scan("bangkok", "2026-10-20T18:00:00Z", office_time_zone=BANGKOK),
        scan("london", "2026-10-20T18:00:00Z", office_time_zone="Europe/London"),
    ]

    assert top_codes(scans, "today") == ["bangkok"]


def test_the_work_week_starts_on_each_offices_own_monday() -> None:
    # 20:00 UTC on Sunday 18 October: already Monday 03:00 in Bangkok, still Sunday 21:00 in London.
    sunday_evening_in_london = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)
    scans = scans_table(
        scan("bangkok-this-week", "2026-10-18T17:30:00Z", office_time_zone=BANGKOK),  # Mon 00:30
        scan("bangkok-last-week", "2026-10-14T03:00:00Z", office_time_zone=BANGKOK),  # Wed 14th
        scan("london-this-week", "2026-10-14T09:00:00Z", office_time_zone="Europe/London"),  # Wed 14th
    )

    rows = top_scans(scans, limit=10, now=sunday_evening_in_london)["this-work-week"]

    assert sorted(row["code"] for row in rows) == ["bangkok-this-week", "london-this-week"]


def test_scans_after_the_build_are_not_counted() -> None:
    assert top_codes([scan("future", "2026-10-21T06:00:00Z", office_time_zone=BANGKOK)], "all-time") == []


def test_unknown_only_ranks_unknown_products_even_below_the_overall_top() -> None:
    scans = scans_table(
        # Two known products outrank the unknown ones overall.
        *(scan("soda", f"2026-10-20T0{n}:00:00Z", office_time_zone=BANGKOK, product_known=True) for n in range(4)),
        *(scan("chips", f"2026-10-20T0{n}:00:00Z", office_time_zone=BANGKOK, product_known=True) for n in range(3)),
        scan("qr-code", "2026-10-20T01:00:00Z", office_time_zone=BANGKOK),
        scan("qr-code", "2026-10-20T02:00:00Z", office_time_zone=BANGKOK),
        scan("8858998581234", "2026-10-20T03:00:00Z", office_time_zone=BANGKOK),
        # Known to OpenFoodFacts but unnamed: not an unknown product.
        scan("unnamed", "2026-10-20T04:00:00Z", office_time_zone=BANGKOK, product_known=True),
    )

    rows = top_scans(scans, limit=2, now=NOW, unknown_only=True)["last-7-days"]

    assert [(row["code"], row["known"]) for row in rows] == [("qr-code", False), ("8858998581234", False)]
    # Share is of all 11 scans in the period, not just the unknown ones.
    assert [row["share"] for row in rows] == [0.1818, 0.0909]


def test_unknown_only_lists_every_period() -> None:
    by_period = top_scans(scans_table(), limit=10, now=NOW, unknown_only=True)

    assert tuple(by_period) == PERIODS

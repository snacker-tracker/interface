"""Tests at the Scan summary seam: a scans table in, daily counts and recent scan rows out."""

from scans_table import scan, scans_table
from snacker.scan_summary import summarise


def test_counts_scans_per_day_oldest_first() -> None:
    scans = scans_table(
        scan("8850999220000", "2023-01-11T02:32:32Z"),
        scan("8850999220000", "2023-01-08T03:10:22Z"),
        scan("8851959132012", "2023-01-08T05:00:00Z"),
    )

    assert summarise(scans, recent_limit=25).daily == [
        {"date": "2023-01-08", "count": 2},
        {"date": "2023-01-11", "count": 1},
    ]


def test_a_scan_counts_on_the_day_it_was_in_its_office_time_zone() -> None:
    # 18:30 UTC on the 22nd is 01:30 on the 23rd in Bangkok (UTC+7).
    scans = scans_table(
        scan("8850999220000", "2026-09-22T18:30:00Z", office_time_zone="Asia/Bangkok"),
        scan("8851959132012", "2026-09-22T18:30:00Z", office_time_zone="UTC"),
    )

    assert summarise(scans, recent_limit=25).daily == [
        {"date": "2026-09-22", "count": 1},
        {"date": "2026-09-23", "count": 1},
    ]


def test_the_day_turns_at_midnight_in_the_office_time_zone() -> None:
    # Bangkok is UTC+7, so its midnight is 17:00 UTC.
    scans = scans_table(
        scan("8850999220000", "2026-09-22T16:59:59Z", office_time_zone="Asia/Bangkok"),
        scan("8851959132012", "2026-09-22T17:00:00Z", office_time_zone="Asia/Bangkok"),
    )

    assert summarise(scans, recent_limit=25).daily == [
        {"date": "2026-09-22", "count": 1},
        {"date": "2026-09-23", "count": 1},
    ]


def test_scans_from_offices_in_different_time_zones_each_count_on_their_own_day() -> None:
    # The same instant is Wednesday morning in Bangkok and still Tuesday evening in London.
    scans = scans_table(
        scan("8850999220000", "2026-09-22T20:00:00Z", location="thailand:bangkok",
             office_time_zone="Asia/Bangkok"),
        scan("5000159484695", "2026-09-22T20:00:00Z", location="uk:london",
             office_time_zone="Europe/London"),
    )

    assert summarise(scans, recent_limit=25).daily == [
        {"date": "2026-09-22", "count": 1},
        {"date": "2026-09-23", "count": 1},
    ]


def test_lists_the_most_recent_scans_newest_first() -> None:
    scans = scans_table(*(
        scan(f"88500000000{minute:02d}", f"2026-09-23T06:{minute:02d}:00Z",
             location="thailand:bangkok:main-kitchen", office_time_zone="Asia/Bangkok")
        for minute in range(27)
    ))

    recent = summarise(scans, recent_limit=25).recent

    assert len(recent) == 25
    assert recent[0] == {
        "product": {"code": "8850000000026", "name": None, "name_source": None, "brands": None, "known": False, "nutri_score": None},
        "location": "thailand:bangkok:main-kitchen",
        "scanned_at": "2026-09-23T06:26:00Z",
        "office_time": "2026-09-23T13:26:00+07:00",
        "office_time_zone": "Asia/Bangkok",
    }
    assert recent[-1]["scanned_at"] == "2026-09-23T06:02:00Z"


def test_no_scans_summarise_to_nothing() -> None:
    summary = summarise(scans_table(), recent_limit=25)

    assert (summary.daily, summary.recent) == ([], [])


def test_scan_rows_name_the_product_or_leave_it_empty_when_unknown() -> None:
    scans = scans_table(
        scan("8851959132012", "2026-09-23T06:01:00Z", product_name="Coca Cola", product_brands="Coke"),
        scan("http://oishidrink.com/m/", "2026-09-23T06:00:00Z"),
    )

    recent = summarise(scans, recent_limit=25).recent

    assert [(row["product"]["code"], row["product"]["name"], row["product"]["brands"]) for row in recent] == [
        ("8851959132012", "Coca Cola", "Coke"),
        ("http://oishidrink.com/m/", None, None),
    ]


def test_counts_scans_by_hour_of_the_day_in_the_office_time_zone() -> None:
    scans = scans_table(
        # 02:15 and 02:45 UTC are 09:15 and 09:45 in Bangkok; 16:59 UTC is 23:59.
        scan("8850999220000", "2026-09-22T02:15:00Z", office_time_zone="Asia/Bangkok"),
        scan("8850999220000", "2026-09-23T02:45:00Z", office_time_zone="Asia/Bangkok"),
        scan("8850999220000", "2026-09-22T16:59:00Z", office_time_zone="Asia/Bangkok"),
    )

    hourly = summarise(scans, recent_limit=25).hourly

    assert [entry["hour"] for entry in hourly] == list(range(24))
    assert {entry["hour"]: entry["count"] for entry in hourly if entry["count"]} == {9: 2, 23: 1}


def test_every_hour_is_listed_even_without_scans() -> None:
    hourly = summarise(scans_table(), recent_limit=25).hourly

    assert hourly == [{"hour": hour, "count": 0} for hour in range(24)]

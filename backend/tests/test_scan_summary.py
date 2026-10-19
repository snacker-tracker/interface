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


def test_lists_the_most_recent_scans_newest_first() -> None:
    scans = scans_table(*(
        scan(f"88500000000{minute:02d}", f"2026-09-23T06:{minute:02d}:00Z",
             location="thailand:bangkok:main-kitchen")
        for minute in range(27)
    ))

    recent = summarise(scans, recent_limit=25).recent

    assert len(recent) == 25
    assert recent[0] == {
        "code": "8850000000026",
        "location": "thailand:bangkok:main-kitchen",
        "scanned_at": "2026-09-23T06:26:00Z",
    }
    assert recent[-1]["scanned_at"] == "2026-09-23T06:02:00Z"


def test_no_scans_summarise_to_nothing() -> None:
    summary = summarise(scans_table(), recent_limit=25)

    assert (summary.daily, summary.recent) == ([], [])

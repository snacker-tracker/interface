"""Tests at the Locations seam: which locations can be selected, what they include, and their time zones."""

import polars as pl
import pytest

from snacker.locations import Locations

SCANS = pl.DataFrame({
    "event_id": ["a", "b", "c"],
    "code": ["8850999220000", "8851959132012", "8850269522902"],
    "location": ["thailand:bangkok", "thailand:bangkok:main-kitchen", "thailand:test"],
})


def test_selectable_locations_are_all_and_every_prefix_of_every_location_scanned() -> None:
    assert Locations.from_scans(SCANS).selectable() == [
        "all",
        "thailand",
        "thailand:bangkok",
        "thailand:bangkok:main-kitchen",
        "thailand:test",
    ]


def test_test_locations_are_selectable_like_any_other() -> None:
    assert "thailand:test" in Locations.from_scans(SCANS).selectable()


def test_all_includes_every_scan() -> None:
    locations = Locations.from_scans(SCANS)

    assert locations.within(SCANS, "all")["event_id"].to_list() == ["a", "b", "c"]


def test_a_location_includes_the_scans_beneath_it_on_whole_segments_only() -> None:
    scans = pl.DataFrame({
        "event_id": ["old", "new", "annex", "elsewhere"],
        "location": [
            "thailand:bangkok",
            "thailand:bangkok:main-kitchen",
            "thailand:bangkok-annex",
            "vietnam:hanoi",
        ],
    })
    locations = Locations.from_scans(scans)

    assert locations.within(scans, "thailand:bangkok")["event_id"].to_list() == ["old", "new"]


def test_a_location_that_is_not_selectable_is_refused() -> None:
    # A partial segment is not a location: `thailand:bang` names nothing.
    with pytest.raises(ValueError, match="not a selectable location: 'thailand:bang'"):
        Locations.from_scans(SCANS).within(SCANS, "thailand:bang")


def test_every_scan_is_in_utc_until_office_time_zones_are_configured() -> None:
    zoned = Locations.from_scans(SCANS).with_office_time_zones(SCANS)

    assert zoned["office_time_zone"].to_list() == ["UTC", "UTC", "UTC"]

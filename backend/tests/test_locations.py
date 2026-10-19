"""Tests at the Locations seam: which locations can be selected, what they include, and their time zones."""

import polars as pl
import pytest

from snacker.locations import Locations

ZONES = {"thailand": "Asia/Bangkok"}

SCANS = pl.DataFrame({
    "event_id": ["a", "b", "c"],
    "code": ["8850999220000", "8851959132012", "8850269522902"],
    "location": ["thailand:bangkok", "thailand:bangkok:main-kitchen", "thailand:test"],
})


def test_selectable_locations_are_all_and_every_prefix_of_every_location_scanned() -> None:
    assert Locations.from_scans(SCANS, ZONES).selectable() == [
        "all",
        "thailand",
        "thailand:bangkok",
        "thailand:bangkok:main-kitchen",
        "thailand:test",
    ]


def test_test_locations_are_selectable_like_any_other() -> None:
    assert "thailand:test" in Locations.from_scans(SCANS, ZONES).selectable()


def test_all_includes_every_scan() -> None:
    locations = Locations.from_scans(SCANS, ZONES)

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
    locations = Locations.from_scans(scans, {"thailand": "Asia/Bangkok", "vietnam": "Asia/Ho_Chi_Minh"})

    assert locations.within(scans, "thailand:bangkok")["event_id"].to_list() == ["old", "new"]


def test_a_location_that_is_not_selectable_is_refused() -> None:
    # A partial segment is not a location: `thailand:bang` names nothing.
    with pytest.raises(ValueError, match="not a selectable location: 'thailand:bang'"):
        Locations.from_scans(SCANS, ZONES).within(SCANS, "thailand:bang")


def test_each_scan_gets_the_time_zone_of_its_longest_matching_location_prefix() -> None:
    scans = pl.DataFrame({
        "event_id": ["kitchen", "remote", "hanoi"],
        "location": ["thailand:bangkok:main-kitchen", "thailand:remote:london", "vietnam:hanoi"],
    })
    zones = {
        "thailand": "Asia/Bangkok",
        "thailand:remote:london": "Europe/London",
        "vietnam": "Asia/Ho_Chi_Minh",
    }

    zoned = Locations.from_scans(scans, zones).with_office_time_zones(scans)

    assert zoned["office_time_zone"].to_list() == ["Asia/Bangkok", "Europe/London", "Asia/Ho_Chi_Minh"]


def test_a_location_without_an_office_time_zone_is_refused() -> None:
    scans = pl.DataFrame({"event_id": ["a", "b"], "location": ["thailand:bangkok", "vietnam:hanoi"]})

    with pytest.raises(ValueError, match="no office time zone for location 'vietnam:hanoi'"):
        Locations.from_scans(scans, ZONES)


def test_time_zone_prefixes_match_whole_segments_only() -> None:
    scans = pl.DataFrame({"event_id": ["a"], "location": ["thailand:bangkok"]})

    with pytest.raises(ValueError, match="no office time zone for location 'thailand:bangkok'"):
        Locations.from_scans(scans, {"thai": "Asia/Bangkok"})


def test_an_unknown_time_zone_name_is_refused() -> None:
    scans = pl.DataFrame({"event_id": ["a"], "location": ["thailand:bangkok"]})

    with pytest.raises(ValueError, match="unknown time zone 'Asia/Bangkokk' for 'thailand'"):
        Locations.from_scans(scans, {"thailand": "Asia/Bangkokk"})

"""Tests at the Locations seam: which locations can be selected, what they include, and their time zones."""

import polars as pl
import pytest

from snacker.locations import Locations

SCANS = pl.DataFrame({
    "event_id": ["a", "b"],
    "code": ["8850999220000", "8851959132012"],
    "location": ["thailand:bangkok", "thailand:bangkok:main-kitchen"],
})


def test_all_is_the_only_selectable_location_for_now() -> None:
    assert Locations.from_scans(SCANS).selectable() == ["all"]


def test_all_includes_every_scan() -> None:
    locations = Locations.from_scans(SCANS)

    assert locations.within(SCANS, "all")["event_id"].to_list() == ["a", "b"]


def test_a_location_that_is_not_selectable_is_refused() -> None:
    with pytest.raises(ValueError, match="not a selectable location: 'mars'"):
        Locations.from_scans(SCANS).within(SCANS, "mars")


def test_every_scan_is_in_utc_until_office_time_zones_are_configured() -> None:
    zoned = Locations.from_scans(SCANS).with_office_time_zones(SCANS)

    assert zoned["office_time_zone"].to_list() == ["UTC", "UTC"]

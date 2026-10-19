"""Locations: which locations can be selected, which scans each includes, and their office time zones.

A location is a colon-separated path (`thailand:bangkok:main-kitchen`) and includes every
location beneath it. Each location's office time zone comes from a map of location
prefixes to IANA time zones, where the longest matching prefix wins.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl

ALL = "all"
SEPARATOR = ":"


@dataclass(frozen=True)
class Locations:
    observed: frozenset[str]
    """Every location some scan came from."""
    zone_by_location: Mapping[str, str]
    """The office time zone of each observed location."""

    @classmethod
    def from_scans(cls, scans: pl.DataFrame, office_time_zones: Mapping[str, str]) -> "Locations":
        """`office_time_zones` maps location prefixes to IANA time zones.

        Fails if a time zone name is unknown, or an observed location has no time zone.
        """
        check_time_zone_names(office_time_zones)
        observed = frozenset(scans["location"].unique().to_list())
        return cls(
            observed=observed,
            zone_by_location={
                location: office_time_zone(location, office_time_zones) for location in observed
            },
        )

    def selectable(self) -> list[str]:
        """`all`, then every prefix of every observed location, in path order."""
        return [ALL, *sorted({prefix for location in self.observed for prefix in prefixes(location)})]

    def within(self, scans: pl.DataFrame, location: str) -> pl.DataFrame:
        """The scans at `location` or anywhere beneath it."""
        if location not in self.selectable():
            raise ValueError(f"not a selectable location: {location!r}")
        if location == ALL:
            return scans
        # Whole segments only: `thailand:bangkok` covers `thailand:bangkok:main-kitchen`
        # but not `thailand:bangkok-annex`.
        return scans.filter(
            (pl.col("location") == location)
            | pl.col("location").str.starts_with(location + SEPARATOR)
        )

    def with_office_time_zones(self, scans: pl.DataFrame) -> pl.DataFrame:
        """Attach each scan's office time zone as an `office_time_zone` column."""
        return scans.with_columns(
            pl.col("location")
            .replace_strict(dict(self.zone_by_location), return_dtype=pl.String())
            .alias("office_time_zone")
        )


def prefixes(location: str) -> list[str]:
    """Every whole-segment prefix of a location, shortest first, ending with the location."""
    segments = location.split(SEPARATOR)
    return [SEPARATOR.join(segments[:depth]) for depth in range(1, len(segments) + 1)]


def office_time_zone(location: str, office_time_zones: Mapping[str, str]) -> str:
    """The time zone of the longest prefix of `location` in the map."""
    for prefix in reversed(prefixes(location)):
        if prefix in office_time_zones:
            return office_time_zones[prefix]
    raise ValueError(f"no office time zone for location {location!r}")


def check_time_zone_names(office_time_zones: Mapping[str, str]) -> None:
    for prefix, time_zone in office_time_zones.items():
        try:
            ZoneInfo(time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone {time_zone!r} for {prefix!r}") from None

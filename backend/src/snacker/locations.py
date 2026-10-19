"""Locations: which locations can be selected, which scans each includes, and their office time zones.

A location is a colon-separated path (`thailand:bangkok:main-kitchen`) and includes every
location beneath it. For now every scan is treated as UTC; ticket 04 adds office time zones.
"""

from dataclasses import dataclass

import polars as pl

ALL = "all"
SEPARATOR = ":"


@dataclass(frozen=True)
class Locations:
    observed: frozenset[str]
    """Every location some scan came from."""

    @classmethod
    def from_scans(cls, scans: pl.DataFrame) -> "Locations":
        return cls(observed=frozenset(scans["location"].unique().to_list()))

    def selectable(self) -> list[str]:
        """`all`, then every prefix of every observed location, in path order."""
        prefixes = {
            SEPARATOR.join(segments[:depth])
            for location in self.observed
            for segments in [location.split(SEPARATOR)]
            for depth in range(1, len(segments) + 1)
        }
        return [ALL, *sorted(prefixes)]

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
        return scans.with_columns(pl.lit("UTC").alias("office_time_zone"))

"""Locations: which locations can be selected, which scans each includes, and their office time zones.

A location is a colon-separated path (`thailand:bangkok:main-kitchen`) and includes every
location beneath it. For now only `all` is selectable and every scan is treated as UTC;
ticket 03 adds the hierarchy and ticket 04 the office time zones.
"""

from dataclasses import dataclass

import polars as pl

ALL = "all"


@dataclass(frozen=True)
class Locations:
    observed: frozenset[str]
    """Every location some scan came from."""

    @classmethod
    def from_scans(cls, scans: pl.DataFrame) -> "Locations":
        return cls(observed=frozenset(scans["location"].unique().to_list()))

    def selectable(self) -> list[str]:
        return [ALL]

    def within(self, scans: pl.DataFrame, location: str) -> pl.DataFrame:
        """The scans at `location` or anywhere beneath it."""
        if location not in self.selectable():
            raise ValueError(f"not a selectable location: {location!r}")
        return scans

    def with_office_time_zones(self, scans: pl.DataFrame) -> pl.DataFrame:
        """Attach each scan's office time zone as an `office_time_zone` column."""
        return scans.with_columns(pl.lit("UTC").alias("office_time_zone"))

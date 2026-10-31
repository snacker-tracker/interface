"""The index files' sections, each a bundle across every selectable location's index file.

Each section is one or more of `IndexFile`'s keys, built by Snacker's own per-section functions
exactly as `write_data` calls them, on the scans within each location. `site_tree` merges them
into whole index files, in `IndexFile`'s key order.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import polars as pl

from scans_example import site
from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.contract import index_path
from snacker.scan_summary import healthiest_and_least_healthy, nutri_score_distribution, period_days, summarise, top_scans

Fragment = Callable[[str, pl.DataFrame], dict[str, Any]]


def bundle(scanned: pl.LazyFrame, fragment: Fragment) -> site.Bundle:
    """`fragment(location, scans within it)` for every selectable location, by its index file's path."""
    described = site.described_scans(scanned)
    locations = site.locations_of(described)
    return {
        index_path(location).as_posix(): fragment(location, locations.within(described, location))
        for location in locations.selectable()
    }


def top_scans_section(scanned: pl.LazyFrame, now: datetime) -> site.Bundle:
    """The index file's `location` (its first key) and `top_scans`."""
    return bundle(scanned, lambda location, scans: {
        "location": location,
        "top_scans": top_scans(scans, limit=TOP_SCANS_LIMIT, now=now),
    })


def top_unknown_scans_section(scanned: pl.LazyFrame, now: datetime) -> site.Bundle:
    return bundle(scanned, lambda _, scans: {
        "top_unknown_scans": top_scans(scans, limit=TOP_SCANS_LIMIT, now=now, unknown_only=True),
    })


def healthiest_and_least_healthy_section(scanned: pl.LazyFrame, now: datetime) -> site.Bundle:
    return bundle(scanned, lambda _, scans: {
        "healthiest_and_least_healthy": healthiest_and_least_healthy(scans, limit=TOP_SCANS_LIMIT, now=now),
    })


def nutri_score_distribution_section(scanned: pl.LazyFrame, now: datetime) -> site.Bundle:
    return bundle(scanned, lambda _, scans: {"nutri_score_distribution": nutri_score_distribution(scans, now=now)})


def period_days_section(scanned: pl.LazyFrame, now: datetime) -> site.Bundle:
    return bundle(scanned, lambda _, scans: {"period_days": period_days(scans, now=now)})


def daily_and_recent_section(scanned: pl.LazyFrame) -> site.Bundle:
    """The index's `daily` and `recent` from Snacker's scan summary (its `hourly` is only for code files)."""

    def fragment(_: str, scans: pl.DataFrame) -> dict[str, Any]:
        summary = summarise(scans, recent_limit=RECENT_SCANS_LIMIT)
        return {"daily": summary.daily, "recent": summary.recent}

    return bundle(scanned, fragment)

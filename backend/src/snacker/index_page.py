"""Index page data: scans per day and the most recent scans."""

from typing import Any

import polars as pl

from snacker.timestamps import DATE_FORMAT, UTC_TIMESTAMP_FORMAT


def daily_counts(scans: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        scans.group_by(pl.col("scanned_at").dt.date().alias("date"))
        .len(name="count")
        .sort("date")
        .with_columns(pl.col("date").dt.to_string(DATE_FORMAT))
        .to_dicts()
    )


def recent_scans(scans: pl.DataFrame, limit: int) -> list[dict[str, Any]]:
    return (
        scans.sort(["scanned_at", "event_id"], descending=True)
        .head(limit)
        .select(
            "code",
            "location",
            pl.col("scanned_at").dt.to_string(UTC_TIMESTAMP_FORMAT),
        )
        .to_dicts()
    )

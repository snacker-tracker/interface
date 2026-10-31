"""Normalise raw scan events into one scans table.

Two eras of scan events exist and are treated identically downstream:
- backfill: imported from the previous system (`source: from-backup`), carries a device `scanned_at`
- live: from the current scanner (`source: scanner`), has no `scanned_at`, so the EventBridge
  envelope `time` (when the event was reported) stands in for it
"""

from datetime import datetime
from pathlib import Path

import polars as pl

from snacker.events import read_events
from snacker.raw import RAW_FILE_SCHEMA, RawEvents, deliveries, watermark
from snacker.timestamps import require_timestamps, utc_timestamps

SCANS_SCHEMA = pl.Schema({
    "event_id": pl.String(),
    "code": pl.String(),
    "location": pl.String(),
    "scanned_at": pl.Datetime("us", "UTC"),
    "scanned_at_source": pl.String(),  # "device" | "reported"
    "origin": pl.String(),  # "backfill" | "live"; kept for debugging only
    "api_key": pl.String(),  # the scanner's API key; null for backfill (see docs/adr/0002)
})

SCANS_TABLE_SCHEMA = pl.Schema({**SCANS_SCHEMA, **RAW_FILE_SCHEMA})
"""The scans table: each scan with the raw file it was first delivered in, for the watermark."""

ORIGIN_BY_SOURCE = {"from-backup": "backfill", "scanner": "live"}


# The envelope fields scans use; anything else in an envelope is ignored.
SCAN_ENVELOPE = {
    "id": pl.String(),
    "source": pl.String(),
    "time": pl.String(),
    "detail": pl.Struct({
        "apiKeyId": pl.String(),
        "payload": pl.Struct({"code": pl.String(), "location": pl.String(), "scanned_at": pl.String()}),
    }),
}


def normalise_scans(raw_dir: Path) -> pl.DataFrame:
    """Every scan, both eras, as one table (SCANS_SCHEMA). Fails on an unknown source or a
    timestamp without a timezone, naming the offending value."""
    events = read_events(raw_dir / "scans", SCAN_ENVELOPE).unnest("detail").unnest("payload")

    unknown = events.filter(~pl.col("source").is_in(list(ORIGIN_BY_SOURCE)))
    if not unknown.is_empty():
        raise ValueError(f"unknown scan source {unknown['source'][0]!r} in event {unknown['id'][0]}")

    scans = events.select(
        pl.col("id").alias("event_id"),
        "code",
        "location",
        # Live scans have no device time, so when the event was reported stands in for it.
        pl.coalesce("scanned_at", "time").alias("scanned_at_text"),
        pl.when(pl.col("scanned_at").is_not_null()).then(pl.lit("device")).otherwise(pl.lit("reported"))
        .alias("scanned_at_source"),
        pl.col("source").replace_strict(ORIGIN_BY_SOURCE).alias("origin"),
        pl.col("apiKeyId").alias("api_key"),
    ).with_columns(utc_timestamps(pl.col("scanned_at_text")).alias("scanned_at"))
    require_timestamps(scans, text="scanned_at_text", parsed="scanned_at")

    # Delivery to S3 is at-least-once, so the same event can land in more than one file.
    return (
        scans.select(SCANS_SCHEMA.names())
        .cast(SCANS_SCHEMA)
        .unique("event_id", keep="first", maintain_order=True)
    )


def read_scans(raw: RawEvents, files: dict[str, datetime]) -> pl.DataFrame:
    """The scans in `files` (SCANS_TABLE_SCHEMA), by `normalise_scans`: one row per event, with the
    file of the delivery it kept."""
    if not files:
        return SCANS_TABLE_SCHEMA.to_frame()
    with raw.downloaded(files) as local:
        scans = normalise_scans(local)
        # The first delivery, as the normaliser keeps the first: it reads the same glob.
        delivered = (
            deliveries(local, "scans", files)
            .unique("id", keep="first", maintain_order=True)
            .rename({"id": "event_id"})
        )
    return scans.join(delivered, on="event_id", how="left", maintain_order="left").cast(SCANS_TABLE_SCHEMA)


def new_scans(raw: RawEvents, table: pl.LazyFrame | None) -> pl.DataFrame | None:
    """The scans the scans `table` lacks, read by ADR 0011's watermark rule (`snacker.raw`), or None
    when there are none.

    With no table, or one with no rows, every scan file is read and every scan returned. Otherwise
    files inside the margin are read again, so scans already in the table are dropped.
    """
    since = watermark(table)
    read = read_scans(raw, raw.since("scans", since))
    if table is None or since is None:
        return read
    new = read.lazy().join(table.select("event_id"), on="event_id", how="anti").collect()
    return None if new.is_empty() else new


def from_table(table: pl.LazyFrame) -> pl.DataFrame:
    """The scans table as `normalise_scans` makes it (SCANS_SCHEMA), without the raw file columns."""
    return table.select(SCANS_SCHEMA.names()).collect().cast(SCANS_SCHEMA)

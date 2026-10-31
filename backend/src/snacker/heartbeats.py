"""Heartbeats: each scanner's periodic sign of life, and what it says about the scanner.

Scanner firmware has sent three heartbeat payload shapes, all carrying the same facts:

- flat, unversioned (v0.1.35): `device_name`, `location`, `version`
- flat with telemetry (v0.1.36): the same keys, plus `serial_number`, `telemetry`, ...
- `schema_version` 2 (v0.1.37+): `device.name`, `device.location`, `app.version`

The EventBridge envelope `time` is when the heartbeat arrived. A scanner's scans are the
ones sent with the API key its heartbeats use (see docs/adr/0002).
"""

from datetime import datetime
from pathlib import Path
import polars as pl

from snacker.contract import LastScan, ScannerStatus
from snacker.events import read_events
from snacker.raw import RAW_FILE_SCHEMA, RawEvents, deliveries, watermark
from snacker.timestamps import UTC_TIMESTAMP_FORMAT, require_timestamps, utc_timestamps

HEARTBEATS_SCHEMA = pl.Schema({
    "scanner": pl.String(),
    "location": pl.String(),
    "app_version": pl.String(),
    "sent_at": pl.Datetime("us", "UTC"),
    "api_key": pl.String(),
})

HEARTBEATS_TABLE_SCHEMA = pl.Schema({**HEARTBEATS_SCHEMA, **RAW_FILE_SCHEMA})
"""The heartbeats table: each scanner's latest heartbeat, with the raw file it came from, for the
watermark."""


# The envelope fields heartbeats use, across all three payload shapes; a field a shape
# lacks reads as null. Anything else in an envelope is ignored.
HEARTBEAT_ENVELOPE = {
    "id": pl.String(),
    "time": pl.String(),
    "detail": pl.Struct({
        "apiKeyId": pl.String(),
        "payload": pl.Struct({
            "schema_version": pl.Int64(),
            # flat shapes
            "device_name": pl.String(),
            "location": pl.String(),
            "version": pl.String(),
            # schema_version 2
            "device": pl.Struct({"name": pl.String(), "location": pl.String()}),
            "app": pl.Struct({"version": pl.String()}),
        }),
    }),
}


def normalise_heartbeats(raw_dir: Path) -> pl.DataFrame:
    """Every heartbeat as one row: which scanner, where it is, its app version, when it was sent.

    Fails on a heartbeat in an unknown shape, or a timestamp without a timezone.
    """
    events = read_events(raw_dir / "heartbeats", HEARTBEAT_ENVELOPE).unnest("detail").unnest("payload")

    v2 = pl.col("schema_version") == 2
    flat = pl.col("schema_version").is_null()
    heartbeats = events.select(
        "id",
        pl.when(v2).then(pl.col("device").struct.field("name"))
        .when(flat).then(pl.col("device_name")).alias("scanner"),
        pl.when(v2).then(pl.col("device").struct.field("location"))
        .when(flat).then(pl.col("location")).alias("location"),
        pl.when(v2).then(pl.col("app").struct.field("version"))
        .when(flat).then(pl.col("version")).alias("app_version"),
        pl.col("time").alias("sent_at_text"),
        utc_timestamps(pl.col("time")).alias("sent_at"),
        pl.col("apiKeyId").alias("api_key"),
    )

    # Any other schema_version, or a shape missing one of these facts, isn't one we know.
    unknown = heartbeats.filter(pl.any_horizontal(pl.col("scanner", "location", "app_version").is_null()))
    if not unknown.is_empty():
        raise ValueError(f"heartbeat in an unknown shape in event {unknown['id'][0]}")
    require_timestamps(heartbeats, text="sent_at_text", parsed="sent_at")

    return heartbeats.select(HEARTBEATS_SCHEMA.names()).cast(HEARTBEATS_SCHEMA)


def latest_heartbeats(heartbeats: pl.DataFrame) -> pl.DataFrame:
    """Each scanner's latest heartbeat, ordered by name. A scanner is at the location its
    latest heartbeat names, so filter by location only after this."""
    return heartbeats.sort("sent_at", descending=True).unique("scanner", keep="first").sort("scanner")


def scanner_statuses(heartbeats: pl.DataFrame, scans: pl.DataFrame) -> list[ScannerStatus]:
    """Each scanner as its latest heartbeat describes it, with its last scan, ordered by name.

    `scans` are all scans, with products attached (see products.with_products): a scanner's
    last scan is found by API key wherever it happened.
    """
    last_scans = (
        scans.filter(pl.col("api_key").is_not_null())
        .sort("scanned_at", descending=True)
        .unique("api_key", keep="first")
        # Renamed so it can't be confused with the heartbeat's own times once joined.
        .select(
            "api_key", pl.col("scanned_at").alias("last_scanned_at"),
            "product",
        )
    )
    rows = latest_heartbeats(heartbeats).join(last_scans, on="api_key", how="left", maintain_order="left")
    return [
        ScannerStatus(
            name=row["scanner"],
            location=row["location"],
            app_version=row["app_version"],
            last_seen=row["sent_at"].strftime(UTC_TIMESTAMP_FORMAT),
            last_scan=None if row["last_scanned_at"] is None else LastScan(
                product=row["product"],
                scanned_at=row["last_scanned_at"].strftime(UTC_TIMESTAMP_FORMAT),
            ),
        )
        for row in rows.iter_rows(named=True)
    ]


def read_heartbeats(raw: RawEvents, files: dict[str, datetime]) -> pl.DataFrame:
    """Every heartbeat in `files` (HEARTBEATS_TABLE_SCHEMA), by `normalise_heartbeats`, each with its raw file."""
    if not files:
        return HEARTBEATS_TABLE_SCHEMA.to_frame()
    with raw.downloaded(files) as local:
        heartbeats = normalise_heartbeats(local)
        # Row for row: the normaliser reads the same glob, and neither drops nor reorders heartbeats.
        delivered = deliveries(local, "heartbeats", files).drop("id")
    if heartbeats.height != delivered.height:
        raise AssertionError("the normaliser's rows don't line up with the raw files' lines")
    return pl.concat([heartbeats, delivered], how="horizontal").cast(HEARTBEATS_TABLE_SCHEMA)


def new_latest_heartbeats(raw: RawEvents, table: pl.LazyFrame | None) -> pl.DataFrame | None:
    """Each scanner's latest heartbeat that is newer than its row in the heartbeats `table`, read by
    ADR 0011's watermark rule (`snacker.raw`), or None when there are none.

    With no table, every heartbeat file is read and every scanner returned; a table with no rows
    reads every file too. Files inside the margin are read again, so a heartbeat no newer than the
    scanner's row is dropped.
    """
    incoming = latest_heartbeats(read_heartbeats(raw, raw.since("heartbeats", watermark(table))))
    if table is None:
        return incoming
    known = table.select("scanner", pl.col("sent_at").alias("known_sent_at")).collect()
    new = (
        incoming.join(known, on="scanner", how="left", maintain_order="left")
        .filter(pl.col("known_sent_at").is_null() | (pl.col("sent_at") > pl.col("known_sent_at")))
        .drop("known_sent_at")
    )
    return None if new.is_empty() else new


def from_table(table: pl.LazyFrame) -> pl.DataFrame:
    """The heartbeats table as `normalise_heartbeats` types it (HEARTBEATS_SCHEMA), without the raw file columns."""
    return table.select(HEARTBEATS_SCHEMA.names()).collect().cast(HEARTBEATS_SCHEMA)

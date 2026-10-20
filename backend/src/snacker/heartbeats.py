"""Heartbeats: each scanner's periodic sign of life, and what it says about the scanner.

Scanner firmware has sent three heartbeat payload shapes, all carrying the same facts:

- flat, unversioned (v0.1.35): `device_name`, `location`, `version`
- flat with telemetry (v0.1.36): the same keys, plus `serial_number`, `telemetry`, ...
- `schema_version` 2 (v0.1.37+): `device.name`, `device.location`, `app.version`

The EventBridge envelope `time` is when the heartbeat arrived. A scanner's scans are the
ones sent with the API key its heartbeats use (see docs/adr/0002).
"""

from pathlib import Path
import polars as pl

from snacker.contract import LastScan, ScannerStatus
from snacker.events import read_events
from snacker.timestamps import UTC_TIMESTAMP_FORMAT, require_timestamps, utc_timestamps

HEARTBEATS_SCHEMA = pl.Schema({
    "scanner": pl.String(),
    "location": pl.String(),
    "app_version": pl.String(),
    "sent_at": pl.Datetime("us", "UTC"),
    "api_key": pl.String(),
})


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


def scanner_statuses(heartbeats: pl.DataFrame, scans: pl.DataFrame) -> list[ScannerStatus]:
    """Each scanner as its latest heartbeat describes it, with its last scan, ordered by name.

    `scans` are all scans, with products attached (see products.with_products): a scanner's
    last scan is found by API key wherever it happened.
    """
    latest_heartbeats = (
        heartbeats.sort("sent_at", descending=True)
        .unique("scanner", keep="first")
        .sort("scanner")
    )
    last_scans = (
        scans.filter(pl.col("api_key").is_not_null())
        .sort("scanned_at", descending=True)
        .unique("api_key", keep="first")
        # Renamed so it can't be confused with the heartbeat's own times once joined.
        .select(
            "api_key", pl.col("scanned_at").alias("last_scanned_at"),
            "code", "product_name", "product_name_source", "product_known", "product_nutri_score",
        )
    )
    rows = latest_heartbeats.join(last_scans, on="api_key", how="left", maintain_order="left")
    return [
        ScannerStatus(
            name=row["scanner"],
            location=row["location"],
            app_version=row["app_version"],
            last_seen=row["sent_at"].strftime(UTC_TIMESTAMP_FORMAT),
            last_scan=None if row["last_scanned_at"] is None else LastScan(
                scanned_at=row["last_scanned_at"].strftime(UTC_TIMESTAMP_FORMAT),
                code=row["code"],
                product_name=row["product_name"],
                name_source=row["product_name_source"],
                known=row["product_known"],
                nutri_score=row["product_nutri_score"],
            ),
        )
        for row in rows.iter_rows(named=True)
    ]

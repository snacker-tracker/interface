"""Heartbeats and scanners: each scanner's latest heartbeat, and the scanners files built from it.

`heartbeats` keeps one row per scanner, its latest heartbeat by Snacker's normaliser, plus the raw
file it came from and that file's last-modified time for ADR 0011's watermark (as `scans` does).
Snacker's `normalise_heartbeats` reads a directory laid out like the raw prefix
(`<dir>/heartbeats/…`), so the files are downloaded into a temporary one under their own keys.
"""

import tempfile
from datetime import timedelta
from pathlib import Path

import polars as pl

from scans_example import site
from scans_example.raw import RawFile, RawSource
from snacker.contract import ScannersFile, scanners_path
from snacker.heartbeats import HEARTBEATS_SCHEMA as SNACKER_HEARTBEATS_SCHEMA
from snacker.heartbeats import latest_heartbeats, normalise_heartbeats, scanner_statuses

HEARTBEATS_SCHEMA = pl.Schema({
    **SNACKER_HEARTBEATS_SCHEMA,
    "raw_key": pl.String(),  # the raw file the heartbeat came from
    "source_last_modified": pl.Datetime("us", "UTC"),  # that file's last-modified time
})

MARGIN = timedelta(minutes=15)


def read_heartbeats(source: RawSource, files: list[RawFile]) -> pl.DataFrame:
    """Every heartbeat in `files`, by Snacker's normaliser, each with its raw file."""
    if not files:
        return HEARTBEATS_SCHEMA.to_frame()
    with tempfile.TemporaryDirectory(prefix="heartbeats-") as scratch:
        raw_dir = Path(scratch)
        for f in files:
            path = raw_dir / f.key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read(f.key))
        heartbeats = normalise_heartbeats(raw_dir)
        files_of_rows = _files_of_rows(raw_dir, files)
    if heartbeats.height != files_of_rows.height:
        raise AssertionError("the normaliser's rows don't line up with the raw files' lines")
    return pl.concat([heartbeats, files_of_rows], how="horizontal").cast(HEARTBEATS_SCHEMA)


def _files_of_rows(raw_dir: Path, files: list[RawFile]) -> pl.DataFrame:
    """Each envelope's raw file, row for row in the order Snacker's normaliser reads them (the same
    glob; it neither drops nor reorders heartbeats)."""
    by_path = pl.DataFrame(
        {
            "path": [str(raw_dir / f.key) for f in files],
            "raw_key": [f.key for f in files],
            "source_last_modified": [f.last_modified for f in files],
        },
        schema={"path": pl.String(), "raw_key": pl.String(), "source_last_modified": pl.Datetime("us", "UTC")},
    )
    return (
        pl.scan_ndjson(str(raw_dir / "heartbeats" / "**" / "*"), schema={"id": pl.String()}, include_file_paths="path")
        .collect()
        .join(by_path, on="path", how="left", maintain_order="left")
        .select("raw_key", "source_last_modified")
    )


def new_latest_heartbeats(source: RawSource, previous: pl.LazyFrame | None) -> pl.DataFrame | None:
    """Each scanner's latest heartbeat that is newer than the one in `previous`, or None if there are none.

    With no table (`previous` is None), every heartbeat file is read and every scanner returned.
    Otherwise files are listed from the day folder before the watermark (the newest source
    last-modified time in the table), and only those modified after the watermark minus 15 minutes
    are read. An empty table reads everything.
    """
    if previous is None:
        return latest_heartbeats(read_heartbeats(source, source.list("heartbeats/")))
    watermark = previous.select(pl.col("source_last_modified").max()).collect().item()
    if watermark is None:
        files = source.list("heartbeats/")
    else:
        listed = source.list("heartbeats/", start_after="heartbeats/" + (watermark - timedelta(days=1)).strftime("%Y/%m/%d/"))
        files = [f for f in listed if f.last_modified > watermark - MARGIN]
    incoming = latest_heartbeats(read_heartbeats(source, files))
    # Files inside the margin are read again: keep only heartbeats newer than the scanner's row.
    known = previous.select("scanner", pl.col("sent_at").alias("known_sent_at")).collect()
    new = (
        incoming.join(known, on="scanner", how="left", maintain_order="left")
        .filter(pl.col("known_sent_at").is_null() | (pl.col("sent_at") > pl.col("known_sent_at")))
        .drop("known_sent_at")
    )
    return None if new.is_empty() else new


def snacker_heartbeats(heartbeats: pl.LazyFrame) -> pl.DataFrame:
    """The `heartbeats` table as Snacker's normaliser types it, without the example's own columns."""
    return heartbeats.select(SNACKER_HEARTBEATS_SCHEMA.names()).collect().cast(SNACKER_HEARTBEATS_SCHEMA)


def scanners_files(heartbeats: pl.LazyFrame, scanned: pl.LazyFrame) -> site.Bundle:
    """Every selectable location's scanners file, as Snacker's `write_data` builds it."""
    described = site.described_scans(scanned)
    locations = site.locations_of(described)
    latest = latest_heartbeats(snacker_heartbeats(heartbeats))
    return {
        scanners_path(location).as_posix(): ScannersFile(
            location=location,
            scanners=scanner_statuses(locations.within(latest, location), described),
        )
        for location in locations.selectable()
    }

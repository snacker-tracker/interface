"""The scans table: Snacker's normaliser over the raw files a run decided to read, with each
scan's raw file and that file's last-modified time added for ADR 0011's watermark.

Snacker's `normalise_scans` reads a directory laid out like the raw prefix (`<dir>/scans/…`),
so the files are downloaded into a temporary one under their own keys. It fails on an unknown
source or a timestamp without a timezone with its own `ValueError`.
"""

import tempfile
from pathlib import Path

import polars as pl

from scans_example.raw import RawFile, RawSource
from snacker.scans import SCANS_SCHEMA as SNACKER_SCANS_SCHEMA
from snacker.scans import normalise_scans

SCANS_SCHEMA = pl.Schema({
    **SNACKER_SCANS_SCHEMA,
    "raw_key": pl.String(),  # the raw file the scan was first delivered in
    "source_last_modified": pl.Datetime("us", "UTC"),  # that file's last-modified time
})


def read_scans(source: RawSource, files: list[RawFile]) -> pl.DataFrame:
    """The scans in `files`, by Snacker's normaliser: one row per event, the first delivery kept."""
    if not files:
        return SCANS_SCHEMA.to_frame()
    with tempfile.TemporaryDirectory(prefix="scans-") as scratch:
        raw_dir = Path(scratch)
        for f in files:
            path = raw_dir / f.key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read(f.key))
        scans = normalise_scans(raw_dir)
        delivered = _first_delivery(raw_dir, files)
    return scans.join(delivered, on="event_id", how="left", maintain_order="left").cast(SCANS_SCHEMA)


def _first_delivery(raw_dir: Path, files: list[RawFile]) -> pl.DataFrame:
    """Each event's first file, in the order Snacker's normaliser reads them (the same glob), so
    an event delivered twice is attributed to the delivery Snacker kept."""
    by_path = pl.DataFrame(
        {
            "path": [str(raw_dir / f.key) for f in files],
            "raw_key": [f.key for f in files],
            "source_last_modified": [f.last_modified for f in files],
        },
        schema={"path": pl.String(), "raw_key": pl.String(), "source_last_modified": pl.Datetime("us", "UTC")},
    )
    return (
        pl.scan_ndjson(str(raw_dir / "scans" / "**" / "*"), schema={"id": pl.String()}, include_file_paths="path")
        .collect()
        .unique("id", keep="first", maintain_order=True)
        .join(by_path, on="path", how="left")
        .select(pl.col("id").alias("event_id"), "raw_key", "source_last_modified")
    )

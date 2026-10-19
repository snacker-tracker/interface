"""Reading raw EventBridge envelopes as delivered to S3."""

from collections.abc import Mapping
from pathlib import Path

import polars as pl


def read_events(directory: Path, schema: Mapping[str, pl.DataType]) -> pl.DataFrame:
    """Every JSON envelope in every file under `directory`, one envelope per line.

    Only the fields in `schema` are read, so envelopes of different shapes (backfill and
    live scans, three heartbeat payloads) load together; a field an envelope lacks is null.
    A directory that doesn't exist (e.g. no heartbeats delivered yet) holds no events.
    """
    # One file becomes one chunk; rechunking avoids a Polars panic (1.44 and 2.0) in
    # when/then over a struct field of a many-chunk column. See repro/ for a minimal case.
    return pl.scan_ndjson(str(directory / "**" / "*"), schema=schema).collect().rechunk()

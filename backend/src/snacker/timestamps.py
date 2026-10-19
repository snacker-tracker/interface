"""Timestamp formats used in the JSON output, and strict parsing of raw event timestamps."""

import polars as pl

UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT = "%Y-%m-%d"

# ISO 8601 with an offset, e.g. "2023-01-08T03:10:22.444637+00:00" or "2026-09-23T06:05:42+00:00".
AWARE_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S%.f%:z"


def utc_timestamps(text: pl.Expr) -> pl.Expr:
    """Parse ISO 8601 timestamps to UTC. A trailing `Z` means UTC; any other offset is converted.

    Text without an offset parses to null rather than being guessed as UTC: pass the
    result to `require_timestamps` to refuse it.
    """
    return (
        text.str.replace(r"Z$", "+00:00")
        .str.to_datetime(AWARE_TIMESTAMP_FORMAT, time_zone="UTC", time_unit="us", strict=False)
    )


def require_timestamps(frame: pl.DataFrame, *, text: str, parsed: str) -> None:
    """Fail on the first row whose `text` is present but didn't parse as a timestamp with an offset."""
    unparsed = frame.filter(pl.col(text).is_not_null() & pl.col(parsed).is_null())
    if not unparsed.is_empty():
        raise ValueError(f"timestamp without a timezone: {unparsed[text][0]!r}")

"""Timestamp formats used in the JSON output, and strict parsing of raw event timestamps."""

from datetime import datetime

UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT = "%Y-%m-%d"


def parse_aware_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp, refusing ones without a timezone rather than guessing UTC."""
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError(f"timestamp without a timezone: {value!r}")
    return moment

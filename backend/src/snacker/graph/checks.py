"""Blocking checks on the example's assets: a check returns a failure message, or None to pass."""

import polars as pl

from stepdag.io import RunContext


def every_scan_has_a_code_and_a_time(scans: pl.DataFrame, context: RunContext) -> str | None:
    """Every scan row has a non-empty code and a scanned-at time."""
    no_code = scans.filter(pl.col("code").is_null() | (pl.col("code").str.strip_chars() == ""))["event_id"].to_list()
    no_time = scans.filter(pl.col("scanned_at").is_null())["event_id"].to_list()
    problems = []
    if no_code:
        problems.append(f"no code in events {', '.join(map(str, no_code))}")
    if no_time:
        problems.append(f"no scanned_at in events {', '.join(map(str, no_time))}")
    return "; ".join(problems) or None

"""Blocking checks on the graph's assets: a check returns a failure message, or None to pass."""

import tempfile
from pathlib import Path
from typing import Any

import polars as pl

from snacker import sections
from snacker.check import contract_violations
from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
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


def keeps_the_contract(tree: dict[str, Any], context: RunContext) -> str | None:
    """`site_tree`'s check: the whole-tree contract check, on a staged copy."""
    with tempfile.TemporaryDirectory() as staging:
        sections.write_files(tree, Path(staging))
        violations = contract_violations(Path(staging), recent_limit=RECENT_SCANS_LIMIT, top_limit=TOP_SCANS_LIMIT)
    if not violations:
        return None
    shown = "; ".join(str(v) for v in violations[:5])
    return f"{len(violations)} contract violations: {shown}"

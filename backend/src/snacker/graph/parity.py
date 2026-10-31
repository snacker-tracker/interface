"""Parity with Snacker's backend: Snacker's own build on a run's inputs, diffed with what the run published."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from snacker.graph import site
from snacker.build import write_data
from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT


def snackers_tree(scans: pl.DataFrame, heartbeats: pl.DataFrame, products: pl.LazyFrame, now: datetime) -> dict[str, bytes]:
    """What Snacker's `write_data` builds from the same scans, heartbeats and products at `now`."""
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "data"
        write_data(
            out,
            scans=scans,
            heartbeats=heartbeats,
            products_parquet=site.snacker_products(products, Path(scratch) / "products.parquet"),
            generated_at=now,
            office_time_zones=site.office_time_zones(),
            recent_limit=RECENT_SCANS_LIMIT,
            top_limit=TOP_SCANS_LIMIT,
        )
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def report(ours: dict[str, bytes], snackers: dict[str, bytes]) -> dict[str, Any]:
    """Files only one tree has, and each differing file with the first place it differs."""
    differing = [
        {"path": path, **first_difference(json.loads(ours[path]), json.loads(snackers[path]))}
        for path in sorted(ours.keys() & snackers.keys())
        if ours[path] != snackers[path]
    ]
    only_ours = sorted(ours.keys() - snackers.keys())
    only_snackers = sorted(snackers.keys() - ours.keys())
    return {
        "identical": not (differing or only_ours or only_snackers),
        "only_ours": only_ours,
        "only_snackers": only_snackers,
        "differing": differing,
    }


def first_difference(ours: Any, snackers: Any, at: str = "$") -> dict[str, Any]:
    """The first JSON path where two values differ, in document order, with both values there."""
    if isinstance(ours, dict) and isinstance(snackers, dict):
        if list(ours) != list(snackers):
            return {"at": at, "ours": list(ours), "snackers": list(snackers)}
        for key in ours:
            if ours[key] != snackers[key]:
                return first_difference(ours[key], snackers[key], f"{at}.{key}")
    elif isinstance(ours, list) and isinstance(snackers, list):
        for i, (a, b) in enumerate(zip(ours, snackers)):
            if a != b:
                return first_difference(a, b, f"{at}[{i}]")
        if len(ours) != len(snackers):
            return {"at": f"{at}[{min(len(ours), len(snackers))}]", "ours": len(ours), "snackers": len(snackers)}
    return {"at": at, "ours": ours, "snackers": snackers}

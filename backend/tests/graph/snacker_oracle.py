"""Snacker's own build, run on the same inputs as a graph run, as the oracle for parity."""

import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from snacker.build import write_data
from snacker.config import RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.heartbeats import HEARTBEATS_SCHEMA, normalise_heartbeats
from snacker.products import extract_products, read_archive
from snacker.scans import normalise_scans


def snacker_tree(raw: Path, food: Path, archive: Path, now: datetime, office_time_zones: Mapping[str, str]) -> dict[str, bytes]:
    """Every file Snacker's build writes from `raw` events, `food` and `archive` at `now`, by path under data/."""
    scans = normalise_scans(raw)
    heartbeats = normalise_heartbeats(raw) if (raw / "heartbeats").is_dir() else HEARTBEATS_SCHEMA.to_frame()
    with tempfile.TemporaryDirectory() as scratch:
        products = Path(scratch) / "products.parquet"
        extract_products(food, scans["code"].unique().to_list(), archive=read_archive(archive)).write_parquet(products)
        out = Path(scratch) / "data"
        write_data(
            out,
            scans=scans,
            heartbeats=heartbeats,
            products_parquet=products,
            generated_at=now,
            office_time_zones=office_time_zones,
            recent_limit=RECENT_SCANS_LIMIT,
            top_limit=TOP_SCANS_LIMIT,
        )
        return files_under(out)


def files_under(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def differences(ours: Mapping[str, bytes], theirs: Mapping[str, bytes]) -> list[str]:
    """The paths we published whose bytes differ from Snacker's, or that Snacker doesn't build."""
    return [path for path, data in ours.items() if theirs.get(path) != data]


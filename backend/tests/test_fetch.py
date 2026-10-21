"""Tests at the fetch seam: an input's location in, a local path to read it from out."""

from collections.abc import Callable
from pathlib import Path

import pytest

from fake_bucket import FakeBucket
from snacker.storage import Bucket, fetch


def opener(buckets: dict[str, FakeBucket]) -> Callable[[str], Bucket]:
    return lambda name: buckets[name]


def test_a_local_path_is_read_where_it_is(tmp_path: Path) -> None:
    assert fetch("../data/raw/data/scanner", tmp_path / "fetched", opener({})) == Path("../data/raw/data/scanner")


def test_an_s3_prefix_is_copied_with_the_layout_under_it(tmp_path: Path) -> None:
    raw = FakeBucket({
        "raw/data/scanner/scans/2026/10/20/a": b"scan\n",
        "raw/data/scanner/heartbeats/2026/10/20/b": b"heartbeat\n",
        "raw/data/scanner-old/scans/c": b"another prefix\n",
        "elsewhere/d": b"elsewhere\n",
    })

    local = fetch(
        "s3://snacker-tracker-prod/raw/data/scanner", tmp_path / "fetched", opener({"snacker-tracker-prod": raw})
    )

    assert sorted(p.relative_to(local).as_posix() for p in local.rglob("*") if p.is_file()) == [
        "heartbeats/2026/10/20/b",
        "scans/2026/10/20/a",
    ]
    assert (local / "scans/2026/10/20/a").read_bytes() == b"scan\n"


def test_an_s3_object_is_copied_to_a_file_of_the_same_name(tmp_path: Path) -> None:
    working = FakeBucket({"products.parquet": b"PAR1", "products.parquet.old/x": b"another prefix\n"})

    local = fetch(
        "s3://snacker-tracker-dev-working/products.parquet",
        tmp_path / "fetched",
        opener({"snacker-tracker-dev-working": working}),
    )

    assert local == tmp_path / "fetched" / "products.parquet"
    assert local.read_bytes() == b"PAR1"


def test_an_s3_location_with_nothing_under_it_stops_the_build(tmp_path: Path) -> None:
    raw = FakeBucket({"raw/data/scanner-old/scans/a": b"another prefix\n"})

    with pytest.raises(FileNotFoundError, match="s3://snacker-tracker-prod/raw/data/scanner"):
        fetch(
            "s3://snacker-tracker-prod/raw/data/scanner", tmp_path / "fetched", opener({"snacker-tracker-prod": raw})
        )

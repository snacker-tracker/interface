"""Tests at the build run's seam: raw events and the products table in S3, the site bucket
published, and an extraction started when the table is missing scanned codes."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from built_output import products_parquet, write_products
from fake_bucket import FakeBucket, opener
from raw_events import heartbeat_v2, live_scan, write_events
from snacker.extraction import OPENFOODFACTS, scanned_codes
from snacker.handlers import Settings, handle_build

SETTINGS = Settings(
    raw="s3://raw/raw/data/scanner",
    products="s3://working/products.parquet",
    archive="s3://working/snacker-archive.csv",
    site="s3://site",
    food=OPENFOODFACTS,
    extract_function="snacker-tracker-dev-extract",
)
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class Extractions:
    """Records each extraction the build starts."""

    def __init__(self) -> None:
        self.started = 0

    def __call__(self) -> None:
        self.started += 1


def under(directory: Path, prefix: str) -> dict[str, bytes]:
    """Every file under `directory`, keyed as it would be under `prefix` in a bucket."""
    return {prefix + p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


@pytest.fixture
def buckets(raw_dir: Path) -> dict[str, FakeBucket]:
    write_events(raw_dir, "scans/2026/10/21/a.jsonl", [live_scan("8851959132012", time="2026-10-21T03:00:00Z")])
    return {
        "raw": FakeBucket(under(raw_dir, "raw/data/scanner/")),
        "working": FakeBucket({"snacker-archive.csv": b"code,name\n"}),
        "site": FakeBucket(),
    }


def put_products(buckets: dict[str, FakeBucket], raw_dir: Path, products: dict[str, tuple[str | None, str | None]]) -> None:
    """The products table (code -> name, brands) in the working bucket."""
    write_products(raw_dir, products)
    buckets["working"].objects["products.parquet"] = products_parquet(raw_dir).read_bytes()


def test_a_table_covering_every_scanned_code_publishes_without_starting_an_extraction(
    buckets: dict[str, FakeBucket], raw_dir: Path
) -> None:
    put_products(buckets, raw_dir, {"8851959132012": ("Coca Cola", "Coke")})
    extractions = Extractions()

    handle_build(SETTINGS, open_bucket=opener(buckets), start_extraction=extractions, now=NOW)

    assert extractions.started == 0
    assert buckets["site"].puts()[-1] == "data/meta.json"


def test_a_scanned_code_missing_from_the_table_starts_one_extraction_and_still_publishes(
    buckets: dict[str, FakeBucket], raw_dir: Path
) -> None:
    put_products(buckets, raw_dir, {"8850999220000": ("Singha Soda", "Singha")})
    extractions = Extractions()

    run = handle_build(SETTINGS, open_bucket=opener(buckets), start_extraction=extractions, now=NOW)

    assert extractions.started == 1
    assert run.extraction_started is True
    assert buckets["site"].puts()[-1] == "data/meta.json"


def test_a_first_build_with_no_table_yet_publishes_every_code_as_unknown_and_starts_an_extraction(
    buckets: dict[str, FakeBucket],
) -> None:
    extractions = Extractions()

    handle_build(SETTINGS, open_bucket=opener(buckets), start_extraction=extractions, now=NOW)

    assert extractions.started == 1
    assert b'"known": false' in buckets["site"].objects["data/codes/8851959132012/product.json"]


CACHED = replace(SETTINGS, cache="s3://working/cache", code_version="sha256:aaaa")


def test_a_build_through_the_cache_publishes_what_a_build_from_raw_does(
    buckets: dict[str, FakeBucket], raw_dir: Path
) -> None:
    write_events(raw_dir, "heartbeats/2026/10/21/h", [
        heartbeat_v2(time="2026-10-21T02:00:00Z", device_name="kitchen"),
        heartbeat_v2(time="2026-10-21T03:00:00Z", device_name="kitchen"),
    ])
    buckets["raw"].objects.update(under(raw_dir, "raw/data/scanner/"))
    put_products(buckets, raw_dir, {"8851959132012": ("Coca Cola", "Coke")})
    from_raw = {**buckets, "site": FakeBucket()}
    handle_build(SETTINGS, open_bucket=opener(from_raw), start_extraction=Extractions(), now=NOW)

    run = handle_build(CACHED, open_bucket=opener(buckets), start_extraction=Extractions(), now=NOW)

    assert buckets["site"].objects == from_raw["site"].objects
    assert {"cache/scans.parquet", "cache/heartbeats.parquet"} <= buckets["working"].objects.keys()
    assert run.raw_files_read == 2


def test_a_later_build_reads_only_new_raw_files_and_publishes_them(buckets: dict[str, FakeBucket]) -> None:
    handle_build(CACHED, open_bucket=opener(buckets), start_extraction=Extractions(), now=NOW)
    raw = buckets["raw"]
    raw.gets.clear()
    key = "raw/data/scanner/scans/2026/10/21/b.jsonl"
    raw.objects[key] = (json.dumps(live_scan("8850999220000", time="2026-10-21T04:00:00Z")) + "\n").encode()
    raw.modified_at[key] = NOW

    handle_build(CACHED, open_bucket=opener(buckets), start_extraction=Extractions(), now=NOW)

    assert key in raw.gets
    assert "data/codes/8850999220000/product.json" in buckets["site"].objects


def test_extraction_reads_scanned_codes_from_the_cache_and_writes_none(buckets: dict[str, FakeBucket]) -> None:
    handle_build(CACHED, open_bucket=opener(buckets), start_extraction=Extractions(), now=NOW)
    buckets["raw"].gets.clear()
    buckets["working"].calls.clear()

    codes = scanned_codes(CACHED.raw, opener(buckets), cache=CACHED.cache, version=CACHED.code_version)

    assert codes == ["8851959132012"]
    assert len(buckets["raw"].gets) == 1  # only the newest scan file, within the margin
    assert buckets["working"].puts() == []

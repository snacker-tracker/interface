"""Tests at the build run's seam: raw events and the products table in S3, the site bucket
published, and an extraction started when the table is missing scanned codes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from built_output import products_parquet, write_products
from fake_bucket import FakeBucket, opener
from raw_events import live_scan, write_events
from snacker.extraction import OPENFOODFACTS
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

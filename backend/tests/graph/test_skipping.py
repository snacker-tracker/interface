"""Which of Snacker's assets compute and which skip, on a small graph run twice (ADR 0006 and Snacker's max ages)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from stepdag import run
from stepdag.assets import Bindings

from graph.food_parquet import food, write_food
from graph.raw_events import (
    heartbeat_v2,
    live_scan,
    with_api_key,
    write_heartbeats,
    write_raw,
)
from snacker.graph.definitions import defs

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
ZONES = {"thailand": "Asia/Bangkok"}
MAX_AGE = {"top_scans", "top_unknown_scans", "healthiest_and_least_healthy", "nutri_score_distribution", "period_days", "site_tree"}
PARENTS_ONLY = {"scanned", "locations_file", "daily_and_recent", "code_pages", "product_files", "scanners"}


@pytest.fixture
def io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Bindings:
    monkeypatch.setenv("SCANS_RAW", str(tmp_path / "raw"))
    monkeypatch.setenv("SCANS_TABLES", str(tmp_path / "tables"))
    monkeypatch.setenv("SCANS_SITE", str(tmp_path / "site"))
    monkeypatch.setenv("SCANS_OFFICE_TIME_ZONES", '{"thailand": "Asia/Bangkok"}')
    return defs.bindings("local")


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    return tmp_path / "raw"


@pytest.fixture
def world(io: Bindings, raw: Path, openfoodfacts: Path) -> Path:
    """A day of scans and one heartbeat, with a copy that knows the scanned code."""
    write_food(openfoodfacts, [food("111", names=[("main", "One")])])
    write_raw(raw, "2026/10/18", "a", [with_api_key(live_scan("111", time="2026-10-18T03:00:00Z"), "key-kitchen")], "2026-10-18T03:05:00+00:00")
    write_heartbeats(raw, "2026/10/18", "a", [heartbeat_v2(time="2026-10-18T09:00:00Z", device_name="kitchen", api_key="key-kitchen")], "2026-10-18T09:05:00+00:00")
    return raw


def test_an_unchanged_second_run_computes_none_of_the_parent_driven_assets(io: Bindings, world: Path) -> None:
    run(defs, io, started_at=NOW)

    second = run(defs, io, started_at=NOW + timedelta(minutes=5))

    assert second.computed == []
    assert PARENTS_ONLY <= set(second.skipped)
    assert MAX_AGE <= set(second.skipped)


def test_products_skips_when_the_copy_and_scans_are_unchanged(io: Bindings, world: Path) -> None:
    first = run(defs, io, started_at=NOW)

    second = run(defs, io, started_at=NOW + timedelta(minutes=5))

    assert "products" in second.skipped
    assert second.pointers["products"] == first.pointers["products"]


def test_after_24_hours_only_the_max_age_assets_compute(io: Bindings, world: Path) -> None:
    run(defs, io, started_at=NOW)

    second = run(defs, io, started_at=NOW + timedelta(hours=25))

    assert set(second.computed) == MAX_AGE
    assert PARENTS_ONLY <= set(second.skipped)
    assert "products" in second.skipped


def test_a_new_scan_recomputes_everything_downstream_of_scanned(io: Bindings, world: Path, raw: Path) -> None:
    run(defs, io, started_at=NOW)
    write_raw(raw, "2026/10/19", "b", [with_api_key(live_scan("111", time="2026-10-19T10:00:00Z"), "key-kitchen")], "2026-10-19T10:05:00+00:00")

    second = run(defs, io, started_at=NOW + timedelta(minutes=5))

    downstream = defs.downstream(["scanned"])
    assert set(second.computed) == {"scans", "scanned"} | downstream
    assert {"heartbeats", "openfoodfacts_copy"} <= set(second.skipped)


def test_a_new_heartbeat_alone_computes_only_heartbeats_scanners_and_site_tree(io: Bindings, world: Path, raw: Path) -> None:
    run(defs, io, started_at=NOW)
    write_heartbeats(raw, "2026/10/19", "b", [heartbeat_v2(time="2026-10-19T10:00:00Z", device_name="rooftop", location="thailand:bangkok:rooftop", api_key="key-rooftop")], "2026-10-19T10:05:00+00:00")

    second = run(defs, io, started_at=NOW + timedelta(minutes=5))

    assert set(second.computed) == {"heartbeats", "scanners", "site_tree"}


def test_a_scan_of_a_code_missing_from_products_computes_products_and_scanned(io: Bindings, world: Path, raw: Path) -> None:
    run(defs, io, started_at=NOW)
    write_raw(raw, "2026/10/19", "b", [with_api_key(live_scan("222", time="2026-10-19T10:00:00Z"), "key-kitchen")], "2026-10-19T10:05:00+00:00")

    second = run(defs, io, started_at=NOW + timedelta(minutes=5))

    assert {"products", "scanned"} | defs.downstream(["scanned"]) <= set(second.computed)


def test_a_new_openfoodfacts_revision_with_download_computes_the_copy_products_scanned_and_code_pages(io: Bindings, world: Path, openfoodfacts: Path) -> None:
    run(defs, io, started_at=NOW)
    write_food(openfoodfacts, [food("111", names=[("main", "One renamed")])])

    second = run(defs, io, {"download": True}, started_at=NOW + timedelta(minutes=5))

    assert {"openfoodfacts_copy", "products", "scanned", "code_pages"} <= set(second.computed)


def test_a_download_run_with_an_unchanged_openfoodfacts_revision_computes_nothing(io: Bindings, world: Path) -> None:
    run(defs, io, started_at=NOW)

    second = run(defs, io, {"download": True}, started_at=NOW + timedelta(minutes=5))

    assert second.computed == []

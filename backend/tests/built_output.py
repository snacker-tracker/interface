"""Running the graph over fixture raw files, and reading what it published."""

import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from graph.food_parquet import food, write_archive, write_food
from snacker.graph.definitions import defs
from stepdag import run

GENERATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
FRONT_IMAGE = re.compile(r"/(front_(\w+))\.(\d+)\.\d+\.jpg$")


def food_parquet(raw_dir: Path) -> Path:
    return raw_dir.parent / "openfoodfacts" / "food.parquet"


def archive_csv(raw_dir: Path) -> Path:
    return raw_dir.parent / "snacker-archive.csv"


def write_products(
    raw_dir: Path,
    products: dict[str, tuple[str | None, str | None]],
    details: dict[str, dict[str, Any]] | None = None,
    archive_names: dict[str, str] | None = None,
) -> None:
    """What OpenFoodFacts and the Snacker archive say of each code: code -> (name, brands), plus
    optional details by code (as the site shows them), and names the Snacker archive gives.

    A code whose name and brands are both None, and that has no details, is one OpenFoodFacts doesn't have.
    """
    rows = []
    for code, (name, brands) in products.items():
        if name is None and brands is None and code not in (details or {}):
            continue
        detail = (details or {}).get(code, {})
        image = FRONT_IMAGE.search(detail.get("image_url") or "")
        rows.append(food(
            code,
            names=[("main", name)] if name else [],
            brands=brands,
            quantity=detail.get("quantity"),
            categories=", ".join(detail.get("categories", [])) or None,
            lang=image.group(2) if image else None,
            front_images={image.group(1): int(image.group(3))} if image else None,
            nutriscore=(detail.get("nutri_score") or "").lower() or None,
            nova_group=detail.get("nova_group"),
            green_score=(detail.get("green_score") or "").lower() or None,
        ))
    write_food(food_parquet(raw_dir), rows)
    write_archive(archive_csv(raw_dir), list((archive_names or {}).items()))


def run_build(raw_dir: Path, out_dir: Path) -> None:
    """A local graph run over `raw_dir`, publishing into `out_dir/data/`, at GENERATED_AT."""
    if not food_parquet(raw_dir).exists():
        write_products(raw_dir, {})
    root = raw_dir.parent
    with environment(
        SCANS_RAW=str(raw_dir),
        SCANS_TABLES=str(root / "tables"),
        SCANS_FILES=str(root / "files"),
        SCANS_SITE=str(out_dir),
        SCANS_OPENFOODFACTS=str(food_parquet(raw_dir)),
        SCANS_ARCHIVE=str(archive_csv(raw_dir)),
    ):
        run(defs, defs.bindings("local"), started_at=GENERATED_AT)


@contextmanager
def environment(**settings: str) -> Iterator[None]:
    """The graph's assets take their settings from the environment only."""
    before = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def read_json(out_dir: Path, relative_path: str) -> Any:
    return json.loads((out_dir / relative_path).read_text())

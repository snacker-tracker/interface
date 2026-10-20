"""Running the build over fixture raw files, and reading what it wrote."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from snacker.build import build
from snacker.products import OPENFOODFACTS_PRODUCT_PAGE, PRODUCTS_SCHEMA

GENERATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def products_parquet(raw_dir: Path) -> Path:
    return raw_dir.parent / "products.parquet"


def write_products(
    raw_dir: Path,
    products: dict[str, tuple[str | None, str | None]],
    details: dict[str, dict[str, Any]] | None = None,
    archive_names: dict[str, str] | None = None,
) -> None:
    """The extracted products table: code -> (name, brands), plus optional details by code,
    and names the Snacker archive gives codes OpenFoodFacts can't name.

    A code whose name and brands are both None, and that has no details, is an unknown product.
    """
    def row(code: str, name: str | None, brands: str | None) -> dict[str, Any]:
        if name is None and brands is None and code not in (details or {}):
            product: dict[str, Any] = {"code": code, "known": False}
        else:
            known = {"known": True, "off_url": OPENFOODFACTS_PRODUCT_PAGE.format(code=code), "categories": []}
            product = {"code": code, "name": name, "brands": brands, **known, **(details or {}).get(code, {})}
        if product.get("name"):
            return {**product, "name_source": "openfoodfacts"}
        if code in (archive_names or {}):
            return {**product, "name": (archive_names or {})[code], "name_source": "snacker-archive"}
        return product

    pl.DataFrame(
        [row(code, name, brands) for code, (name, brands) in products.items()],
        schema=PRODUCTS_SCHEMA,
    ).write_parquet(products_parquet(raw_dir))


def run_build(raw_dir: Path, out_dir: Path) -> None:
    if not products_parquet(raw_dir).exists():
        write_products(raw_dir, {})
    build(
        raw_dir=raw_dir,
        out_dir=out_dir,
        products_parquet=products_parquet(raw_dir),
        generated_at=GENERATED_AT,
    )


def read_json(out_dir: Path, relative_path: str) -> Any:
    return json.loads((out_dir / relative_path).read_text())

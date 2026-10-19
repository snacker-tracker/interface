"""Fixture builder for an OpenFoodFacts-style food parquet, with the real column types."""

from pathlib import Path
from typing import Any

import polars as pl

NAME_ENTRY = pl.Struct({"lang": pl.String(), "text": pl.String()})


def food_product(code: str, *, names: dict[str, str] | None, brands: str | None = None) -> dict[str, Any]:
    """`names` maps a language (`main`, `en`, `th`, ...) to the product name in it; None for no names."""
    return {
        "code": code,
        "product_name": None if names is None else [{"lang": lang, "text": text} for lang, text in names.items()],
        "brands": brands,
        "quantity": None,  # a column the extraction doesn't need
    }


def write_food_parquet(path: Path, *products: dict[str, Any]) -> Path:
    pl.DataFrame(
        list(products),
        schema={
            "code": pl.String(),
            "product_name": pl.List(NAME_ENTRY),
            "brands": pl.String(),
            "quantity": pl.String(),
        },
    ).write_parquet(path)
    return path

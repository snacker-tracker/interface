"""Fixture builder for an OpenFoodFacts-style food parquet, with the real column types."""

from pathlib import Path
from typing import Any

import polars as pl

NAME_ENTRY = pl.Struct({"lang": pl.String(), "text": pl.String()})
SIZE = pl.Struct({"h": pl.Int32(), "w": pl.Int32()})
IMAGE = pl.Struct({
    "key": pl.String(),
    "imgid": pl.Int32(),
    "rev": pl.Int32(),
    "sizes": pl.Struct({"100": SIZE, "200": SIZE, "400": SIZE, "full": SIZE}),
    "uploaded_t": pl.Int64(),
    "uploader": pl.String(),
})


def image(key: str, rev: int | None = None) -> dict[str, Any]:
    """An entry of `images`: numbered keys are raw uploads; `front_th` etc. are selected images."""
    return {"key": key, "imgid": None, "rev": rev, "sizes": None, "uploaded_t": None, "uploader": None}


def food_product(
    code: str,
    *,
    names: dict[str, str] | None,
    brands: str | None = None,
    quantity: str | None = None,
    categories: str | None = None,
    lang: str | None = None,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`names` maps a language (`main`, `en`, `th`, ...) to the product name in it; None for no names."""
    return {
        "code": code,
        "product_name": None if names is None else [{"lang": lang, "text": text} for lang, text in names.items()],
        "brands": brands,
        "quantity": quantity,
        "categories": categories,
        "lang": lang,
        "images": images,
        "nova_group": None,  # a column the extraction doesn't need
    }


def write_food_parquet(path: Path, *products: dict[str, Any]) -> Path:
    pl.DataFrame(
        list(products),
        schema={
            "code": pl.String(),
            "product_name": pl.List(NAME_ENTRY),
            "brands": pl.String(),
            "quantity": pl.String(),
            "categories": pl.String(),
            "lang": pl.String(),
            "images": pl.List(IMAGE),
            "nova_group": pl.Int32(),
        },
    ).write_parquet(path)
    return path

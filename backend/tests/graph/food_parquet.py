"""A small `food.parquet` in OpenFoodFacts's real column shapes (those Snacker's extraction reads),
and a Snacker archive CSV with its real columns."""

from pathlib import Path
from typing import Any

import polars as pl

SIZE = pl.Struct({"h": pl.Int32(), "w": pl.Int32()})
IMAGE = pl.Struct({
    "key": pl.String(),
    "imgid": pl.Int32(),
    "rev": pl.Int32(),
    "sizes": pl.Struct({"100": SIZE, "200": SIZE, "400": SIZE, "full": SIZE}),
    "uploaded_t": pl.Int64(),
    "uploader": pl.String(),
})

FOOD_SCHEMA = pl.Schema({
    "code": pl.String(),
    "product_name": pl.List(pl.Struct({"lang": pl.String(), "text": pl.String()})),
    "brands": pl.String(),
    "quantity": pl.String(),
    "categories": pl.String(),
    "lang": pl.String(),
    "images": pl.List(IMAGE),
    "nutriscore_grade": pl.String(),
    "nova_group": pl.Int32(),
    "environmental_score_grade": pl.String(),
})


def food(
    code: str,
    *,
    names: list[tuple[str, str | None]] | None = None,
    brands: str | None = None,
    nutriscore: str | None = None,
    quantity: str | None = None,
    categories: str | None = None,
    lang: str | None = None,
    front_images: dict[str, int] | None = None,
    nova_group: int | None = None,
    green_score: str | None = None,
) -> dict[str, Any]:
    """One OpenFoodFacts product. `names` are (lang, text) pairs; OpenFoodFacts marks the main one `main`.
    `front_images` maps a selected image's key (`front_th`) to its revision."""
    return {
        "code": code,
        "product_name": [{"lang": lang, "text": text} for lang, text in (names or [])],
        "brands": brands,
        "quantity": quantity,
        "categories": categories,
        "lang": lang,
        "images": [
            {"key": key, "imgid": None, "rev": rev, "sizes": None, "uploaded_t": None, "uploader": None}
            for key, rev in (front_images or {}).items()
        ],
        "nutriscore_grade": nutriscore,
        "nova_group": nova_group,
        "environmental_score_grade": green_score,
    }


def write_food(path: Path, products: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(products, schema=FOOD_SCHEMA).write_parquet(path)
    return path


def write_archive(path: Path, rows: list[tuple[str, str]]) -> Path:
    """A Snacker archive CSV with the real columns; only `code` and `name` matter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["code,name,created_at,updated_at,url,categories"]
    lines += [f'{code},"{name}",2019-10-31 09:34:37.713+00,2019-10-31 09:34:37.713+00,,' for code, name in rows]
    path.write_text("\n".join(lines) + "\n")
    return path

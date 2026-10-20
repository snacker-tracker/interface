"""Fixture builder for a normalised scans table with office time zones and products attached."""

import uuid
from datetime import datetime

import polars as pl


def scan(
    code: str,
    scanned_at: str,
    *,
    location: str = "thailand:bangkok",
    office_time_zone: str = "UTC",
    product_name: str | None = None,
    product_name_source: str | None = None,
    product_brands: str | None = None,
    product_known: bool = False,
    product_nutri_score: str | None = None,
) -> dict[str, object]:
    return {
        "event_id": str(uuid.uuid4()),
        "code": code,
        "location": location,
        "scanned_at": datetime.fromisoformat(scanned_at),
        "office_time_zone": office_time_zone,
        "product_name": product_name,
        # A fixture name is OpenFoodFacts's unless it says otherwise.
        "product_name_source": product_name_source or ("openfoodfacts" if product_name else None),
        "product_brands": product_brands,
        "product_known": product_known,
        "product_nutri_score": product_nutri_score,
    }


def scans_table(*scans: dict[str, object]) -> pl.DataFrame:
    return pl.DataFrame(
        list(scans),
        schema={
            "event_id": pl.String(),
            "code": pl.String(),
            "location": pl.String(),
            "scanned_at": pl.Datetime("us", "UTC"),
            "office_time_zone": pl.String(),
            "product_name": pl.String(),
            "product_name_source": pl.String(),
            "product_brands": pl.String(),
            "product_known": pl.Boolean(),
            "product_nutri_score": pl.String(),
        },
    )

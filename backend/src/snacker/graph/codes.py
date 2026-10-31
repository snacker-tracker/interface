"""Code pages and product files, as Snacker's `write_data` and `write_code_files` build them."""

import tempfile
from pathlib import Path

import polars as pl

from snacker.graph import site
from snacker.config import RECENT_SCANS_LIMIT
from snacker.contract import CodeScansFile, ProductFile, code_scans_path, product_path
from snacker.products import product_files as snacker_product_files
from snacker.scan_summary import summarise


def code_pages(scanned: pl.LazyFrame) -> site.Bundle:
    """Each scanned code's daily, hourly and recent scans, for every selectable location where it was scanned."""
    described = site.described_scans(scanned)
    locations = site.locations_of(described)
    bundle: site.Bundle = {}
    for (code,), code_scans in described.group_by("code"):
        for location in locations.selectable():
            scans_within = locations.within(code_scans, location)
            if scans_within.is_empty():
                continue
            summary = summarise(scans_within, recent_limit=RECENT_SCANS_LIMIT)
            bundle[code_scans_path(code, location).as_posix()] = CodeScansFile(
                code=code,
                location=location,
                daily=summary.daily,
                hourly=summary.hourly,
                recent=summary.recent,
            )
    return bundle


def product_files(scanned: pl.LazyFrame, products: pl.LazyFrame) -> site.Bundle:
    """Each scanned code's product file; a code with no products row is an unknown product."""
    codes = site.described_scans(scanned).get_column("code").unique()
    with tempfile.TemporaryDirectory() as scratch:
        files = snacker_product_files(site.snacker_products(products, Path(scratch) / "products.parquet"))
    return {
        product_path(code).as_posix(): files.get(code, ProductFile(code=code, known=False, product=None))
        for code in codes
    }

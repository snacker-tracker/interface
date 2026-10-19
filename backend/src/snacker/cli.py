"""Command line entry point.

    snacker extract-products --raw <scanner dir> --food <food.parquet> --products <products.parquet>
    snacker build --raw <scanner dir> --products <products.parquet> --out <output dir>
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from snacker.build import build
from snacker.products import update_products
from snacker.scans import normalise_scans

RAW_HELP = "Raw scanner data directory, containing scans/."
PRODUCTS_HELP = "The extracted products table (written by extract-products)."


def main() -> None:
    parser = argparse.ArgumentParser(prog="snacker")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_command = commands.add_parser(
        "extract-products",
        help="Look up scanned codes in the OpenFoodFacts food parquet. Skipped when every "
        "scanned code was already looked up.",
    )
    extract_command.add_argument("--raw", type=Path, required=True, help=RAW_HELP)
    extract_command.add_argument("--food", type=Path, required=True, help="OpenFoodFacts food.parquet.")
    extract_command.add_argument("--products", type=Path, required=True, help=PRODUCTS_HELP)
    extract_command.add_argument(
        "--force", action="store_true", help="Extract even if every scanned code was already looked up."
    )

    build_command = commands.add_parser("build", help="Build the static JSON for the interface.")
    build_command.add_argument("--raw", type=Path, required=True, help=RAW_HELP)
    build_command.add_argument("--products", type=Path, required=True, help=PRODUCTS_HELP)
    build_command.add_argument(
        "--out", type=Path, required=True,
        help="Output directory; JSON is written under <out>/data/.",
    )

    args = parser.parse_args()
    if args.command == "extract-products":
        codes = normalise_scans(args.raw)["code"].unique().to_list()
        if update_products(args.food, codes, args.products, force=args.force):
            named = pl.read_parquet(args.products)["name"].is_not_null().sum()
            print(f"Looked up {len(codes)} scanned codes; {named} have a product name. Wrote {args.products}")
        else:
            print(f"Every scanned code is already in {args.products}; nothing to do (use --force to redo)")
    else:
        build(
            raw_dir=args.raw,
            products_parquet=args.products,
            out_dir=args.out,
            generated_at=datetime.now(UTC),
        )
        print(f"Built {args.out / 'data'}")

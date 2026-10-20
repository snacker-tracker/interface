"""Command line entry point.

    snacker extract-products --raw <scanner dir> --food <food.parquet> --products <products.parquet> [--archive <codes.csv>]
    snacker build --raw <scanner dir> --products <products.parquet> --out <output dir>
    snacker check --out <output dir>
    snacker schema --out <schema file>
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from snacker.build import ContractBroken, build
from snacker.check import Violation, contract_violations
from snacker.products import read_archive, update_products
from snacker.schema import schema_json
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
        "--archive", type=Path,
        help="The Snacker archive CSV (codes.csv): names for products OpenFoodFacts can't name. "
        "Without it, names come from OpenFoodFacts only.",
    )
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

    check_command = commands.add_parser(
        "check", help="Check a built output against the output contract (the build does this itself)."
    )
    check_command.add_argument("--out", type=Path, required=True, help="Output directory holding data/.")

    schema_command = commands.add_parser(
        "schema", help="Write the JSON Schema of the static JSON, generated from the output contract."
    )
    schema_command.add_argument(
        "--out", type=Path, required=True, help="Schema file to write, e.g. ../contract/static-json.schema.json."
    )

    args = parser.parse_args()
    if args.command == "schema":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(schema_json())
        print(f"Wrote {args.out}")
    elif args.command == "extract-products":
        codes = normalise_scans(args.raw)["code"].unique().to_list()
        archive = read_archive(args.archive) if args.archive else None
        if archive and archive.duplicated:
            print(f"The archive records these codes more than once, so they get no archive name: {', '.join(archive.duplicated)}")
        if update_products(args.food, codes, args.products, archive=archive, force=args.force):
            sources = pl.read_parquet(args.products)["name_source"].value_counts()
            named = dict(zip(sources["name_source"].to_list(), sources["count"].to_list()))
            print(
                f"Looked up {len(codes)} scanned codes; {named.get('openfoodfacts', 0)} named by OpenFoodFacts, "
                f"{named.get('snacker-archive', 0)} by the Snacker archive. Wrote {args.products}"
            )
        else:
            print(f"Every scanned code is already in {args.products}; nothing to do (use --force to redo)")
    elif args.command == "check":
        violations = contract_violations(args.out / "data")
        if violations:
            fail(f"{args.out / 'data'} breaks the output contract", violations)
        print(f"{args.out / 'data'} keeps the output contract")
    else:
        try:
            build(
                raw_dir=args.raw,
                products_parquet=args.products,
                out_dir=args.out,
                generated_at=datetime.now(UTC),
            )
        except ContractBroken as broken:
            fail(f"Not published: {broken}. The previous data is unchanged", broken.violations)
        print(f"Built {args.out / 'data'}")


def fail(message: str, violations: list[Violation], *, shown: int = 50) -> None:
    print(f"{message}:", file=sys.stderr)
    for violation in violations[:shown]:
        print(f"  {violation}", file=sys.stderr)
    if len(violations) > shown:
        print(f"  ... and {len(violations) - shown} more", file=sys.stderr)
    sys.exit(1)

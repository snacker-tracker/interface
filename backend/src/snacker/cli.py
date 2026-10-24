"""Command line entry point.

    snacker extract-products --raw <scanner dir | s3://…> --food <food.parquet | hf://…> --products <products.parquet | s3://…>
        [--archive <codes.csv | s3://…>] [--cache <cache dir | s3://…>]
    snacker build --raw <scanner dir | s3://…> --products <products.parquet | s3://…> --out <output dir | s3://site-bucket>
        [--cache <cache dir | s3://…>]
    snacker check --out <output dir>
    snacker schema --out <schema file>
"""

import argparse
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from snacker.build import ContractBroken, build
from snacker.check import Violation, contract_violations
from snacker.event_cache import load_events
from snacker.extraction import scanned_codes, signed_hf_url, update_products_at
from snacker.schema import schema_json
from snacker.storage import S3_SCHEME, S3Bucket, fetch, report_s3_operations

RAW_HELP = "Raw scanner data directory, containing scans/."
PRODUCTS_HELP = "The extracted products table (written by extract-products)."
S3_HELP = "Or an s3:// URI, copied to local disk first."
CACHE_HELP = (
    "Where earlier runs left the scans and heartbeats they read, a directory or an s3:// prefix, "
    "so only newer raw files are read (ADR 0011). Stamped with the git commit; with uncommitted "
    "changes to the code, raw is read in full and the cache left alone."
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="snacker")
    commands = parser.add_subparsers(dest="command", required=True)

    extract_command = commands.add_parser(
        "extract-products",
        help="Look up scanned codes in the OpenFoodFacts food parquet. Skipped when every "
        "scanned code was already looked up.",
    )
    extract_command.add_argument("--raw", required=True, help=f"{RAW_HELP} {S3_HELP}")
    extract_command.add_argument(
        "--food", required=True,
        help="OpenFoodFacts food.parquet, or hf://datasets/openfoodfacts/product-database/food.parquet "
        "(resolved to its signed CDN URL only if the table must be written).",
    )
    extract_command.add_argument("--products", required=True, help=f"{PRODUCTS_HELP} {S3_HELP}")
    extract_command.add_argument(
        "--archive",
        help="The Snacker archive CSV (codes.csv): names for products OpenFoodFacts can't name. "
        f"Without it, names come from OpenFoodFacts only. {S3_HELP}",
    )
    extract_command.add_argument(
        "--force", action="store_true", help="Extract even if every scanned code was already looked up."
    )
    extract_command.add_argument("--cache", help=f"{CACHE_HELP} Read only; build writes it.")

    build_command = commands.add_parser("build", help="Build the static JSON for the interface.")
    build_command.add_argument("--raw", required=True, help=f"{RAW_HELP} {S3_HELP}")
    build_command.add_argument("--products", required=True, help=f"{PRODUCTS_HELP} {S3_HELP}")
    build_command.add_argument(
        "--out", required=True,
        help="Output directory, JSON written under <out>/data/; or s3://<site bucket>, whose "
        "data/ gets only the files that changed.",
    )
    build_command.add_argument("--cache", help=CACHE_HELP)

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
    try:
        dispatch(args)
    finally:
        report_s3_operations()


def dispatch(args: argparse.Namespace) -> None:
    if args.command == "schema":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(schema_json())
        print(f"Wrote {args.out}")
    elif args.command == "extract-products":
        run_extraction(args.raw, args.food, args.products, args.archive, force=args.force, cache=args.cache)
    elif args.command == "check":
        violations = contract_violations(args.out / "data")
        if violations:
            fail(f"{args.out / 'data'} breaks the output contract", violations)
        print(f"{args.out / 'data'} keeps the output contract")
    else:
        run_build(args.raw, args.products, args.out, cache=args.cache)


def run_extraction(raw: str, food: str, products: str, archive: str | None, *, force: bool, cache: str | None) -> None:
    """Extract from local, Hugging Face or S3 inputs, to a local or S3 products table."""
    codes = scanned_codes(raw, S3Bucket, cache=cache, version=code_version(Path(__file__).parent))
    update = update_products_at(
        food, codes, products, archive=archive, force=force, open_bucket=S3Bucket, resolve_hf=signed_hf_url
    )
    if update.duplicated:
        print(f"The archive records these codes more than once, so they get no archive name: {', '.join(update.duplicated)}")
    if update.extracted:
        print(
            f"Looked up {len(codes)} scanned codes; {update.named.get('openfoodfacts', 0)} named by OpenFoodFacts, "
            f"{update.named.get('snacker-archive', 0)} by the Snacker archive. Wrote {products}"
        )
    else:
        print(f"Every scanned code is already in {products}; nothing to do (use --force to redo)")


def run_build(raw: str, products: str, out: str, *, cache: str | None) -> None:
    """Build from local or S3 inputs, to a local directory or a site bucket."""
    events = load_events(raw, cache=cache, version=code_version(Path(__file__).parent), open_bucket=S3Bucket)
    with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
        site = None
        out_dir = Path(out)
        if out.startswith(S3_SCHEME):
            bucket_name = out.removeprefix(S3_SCHEME).rstrip("/")
            if "/" in bucket_name:
                sys.exit(f"--out {out}: give the site bucket alone; the build writes its data/")
            site, out_dir = S3Bucket(bucket_name), Path(scratch) / "out"
        try:
            published = build(
                scans=events.scans,
                heartbeats=events.heartbeats,
                products_parquet=fetch(products, Path(scratch) / "products", S3Bucket),
                out_dir=out_dir,
                generated_at=datetime.now(UTC),
                site=site,
            )
        except ContractBroken as broken:
            fail(f"Not published: {broken}. The previous data is unchanged", broken.violations)
    if published is None:
        print(f"Built {out_dir / 'data'}")
    else:
        print(f"Published to {out}: uploaded {len(published.uploaded)} files, deleted {len(published.deleted)}")
        for key in published.uploaded:
            print(f"  + {key}")
        for key in published.deleted:
            print(f"  - {key}")


def code_version(directory: Path) -> str | None:
    """The git commit the code in `directory` is at, or None outside git or with uncommitted
    changes there: a cache stamped with it must describe exactly this code."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=directory, check=True, capture_output=True, text=True).stdout

    try:
        if git("status", "--porcelain", "--", "."):
            return None
        return git("rev-parse", "HEAD").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def fail(message: str, violations: list[Violation], *, shown: int = 50) -> None:
    print(f"{message}:", file=sys.stderr)
    for violation in violations[:shown]:
        print(f"  {violation}", file=sys.stderr)
    if len(violations) > shown:
        print(f"  ... and {len(violations) - shown} more", file=sys.stderr)
    sys.exit(1)

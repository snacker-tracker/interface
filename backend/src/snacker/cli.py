"""Command line entry point.

    snacker check --out <output dir>
    snacker schema --out <schema file>

The site's data is built by the graph: `stepdag run snacker.graph.definitions:defs` (see
backend/README.md).
"""

import argparse
import sys
from pathlib import Path

from snacker.check import Violation, contract_violations
from snacker.schema import schema_json


def main() -> None:
    parser = argparse.ArgumentParser(prog="snacker")
    commands = parser.add_subparsers(dest="command", required=True)

    check_command = commands.add_parser(
        "check", help="Check a built output against the output contract (the graph does this itself)."
    )
    check_command.add_argument("--out", type=Path, required=True, help="Output directory holding data/.")

    schema_command = commands.add_parser(
        "schema", help="Write the JSON Schema of the static JSON, generated from the output contract."
    )
    schema_command.add_argument(
        "--out", type=Path, required=True, help="Schema file to write, e.g. ../contract/static-json.schema.json."
    )

    dispatch(parser.parse_args())


def dispatch(args: argparse.Namespace) -> None:
    if args.command == "schema":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(schema_json())
        print(f"Wrote {args.out}")
    else:
        violations = contract_violations(args.out / "data")
        if violations:
            fail(f"{args.out / 'data'} breaks the output contract", violations)
        print(f"{args.out / 'data'} keeps the output contract")


def fail(message: str, violations: list[Violation], *, shown: int = 50) -> None:
    print(f"{message}:", file=sys.stderr)
    for violation in violations[:shown]:
        print(f"  {violation}", file=sys.stderr)
    if len(violations) > shown:
        print(f"  ... and {len(violations) - shown} more", file=sys.stderr)
    sys.exit(1)

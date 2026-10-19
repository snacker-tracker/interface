"""Command line entry point: `snacker build --raw <scanner dir> --out <output dir>`."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from snacker.build import build


def main() -> None:
    parser = argparse.ArgumentParser(prog="snacker")
    commands = parser.add_subparsers(dest="command", required=True)

    build_command = commands.add_parser("build", help="Build the static JSON for the interface.")
    build_command.add_argument(
        "--raw", type=Path, required=True,
        help="Raw scanner data directory, containing scans/ (and later heartbeats/).",
    )
    build_command.add_argument(
        "--out", type=Path, required=True,
        help="Output directory; JSON is written under <out>/data/.",
    )

    args = parser.parse_args()
    build(raw_dir=args.raw, out_dir=args.out, generated_at=datetime.now(UTC))
    print(f"Built {args.out / 'data'}")

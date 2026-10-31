"""Snacker's site data tree, built from section bundles and published as Snacker publishes it.

A bundle is `{site path: contract file or fragment}`, a path relative to the site's `data/`.
`site_tree` merges the bundles into whole files and publishes them with Snacker's own
`publish_to_bucket` (ADR 0004), to a directory locally or the shadow bucket in Lambda.
"""

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from snacker.build import format_utc, write_json
from snacker.check import contract_violations
from snacker.config import OFFICE_TIME_ZONES, RECENT_SCANS_LIMIT, TOP_SCANS_LIMIT
from snacker.contract import CONTRACT_VERSION, MetaFile, meta_path
from snacker.locations import Locations
from snacker.products import PRODUCTS_SCHEMA, SCANNED_PRODUCT
from snacker.scans import SCANS_SCHEMA
from snacker.storage import Bucket, DirectoryBucket, S3Bucket, publish_to_bucket
from stepdag import Pointer, RunContext

Bundle = dict[str, Any]


def office_time_zones() -> Mapping[str, str]:
    """`$SCANS_OFFICE_TIME_ZONES` (JSON), else Snacker's configured office time zones."""
    configured = os.environ.get("SCANS_OFFICE_TIME_ZONES")
    return json.loads(configured) if configured else OFFICE_TIME_ZONES


def snacker_scans(scans: pl.LazyFrame) -> pl.DataFrame:
    """The `scans` table as Snacker's normaliser makes it, without the example's own columns."""
    return scans.select(SCANS_SCHEMA.names()).collect().cast(SCANS_SCHEMA)


def snacker_products(products: pl.LazyFrame, path: Path) -> Path:
    """Write the `products` table as Snacker's products parquet (its Enums restored), for its functions that read one."""
    products.select(PRODUCTS_SCHEMA.names()).collect().cast(PRODUCTS_SCHEMA).write_parquet(path)
    return path


def described_scans(scanned: pl.LazyFrame) -> pl.DataFrame:
    """`scanned` with the types Snacker's functions expect: Delta stores Enums as text."""
    frame = scanned.collect()
    return frame.cast(pl.Schema({**dict(SCANS_SCHEMA.items()), "product": SCANNED_PRODUCT}))


def locations_of(scans: pl.DataFrame) -> Locations:
    return Locations.from_scans(scans, office_time_zones())


def meta(generated_at: datetime) -> Bundle:
    return {meta_path().as_posix(): MetaFile(generated_at=format_utc(generated_at), contract_version=CONTRACT_VERSION)}


def merged(bundles: list[Bundle]) -> dict[str, Any]:
    """The whole tree. A path in several bundles is one file made of their fragments, in bundle order."""
    tree: dict[str, Any] = {}
    for bundle in bundles:
        for path, content in bundle.items():
            if path in tree and isinstance(tree[path], dict) and isinstance(content, dict):
                tree[path] = {**tree[path], **content}
            else:
                tree[path] = content
    return tree


def write_tree(tree: Mapping[str, Any], root: Path) -> None:
    """Write every file exactly as Snacker's build writes it, for publishing."""
    _write_files(tree, root)


def _write_files(tree: Mapping[str, Any], root: Path) -> None:
    for path, content in tree.items():
        write_json(root / path, content)


def keeps_the_contract(tree: dict[str, Any], context: RunContext) -> str | None:
    """`site_tree`'s blocking check: Snacker's whole-tree contract check, on a staged copy."""
    with tempfile.TemporaryDirectory() as staging:
        _write_files(tree, Path(staging))
        violations = contract_violations(Path(staging), recent_limit=RECENT_SCANS_LIMIT, top_limit=TOP_SCANS_LIMIT)
    if not violations:
        return None
    shown = "; ".join(str(v) for v in violations[:5])
    return f"{len(violations)} contract violations: {shown}"


class SiteIO:
    """Publishes `site_tree`'s value with Snacker's diff-publish into `<location>/data/`.

    `$SCANS_SITE` is a directory locally, or `s3://<bucket>` in Lambda. The pointer names the tree
    and its `generated_at`; `latest()` reads `data/meta.json`.
    """

    name = "site"

    def __init__(self, location: str) -> None:
        self.location = location

    def _bucket(self) -> Bucket:
        if self.location.startswith("s3://"):
            return S3Bucket(self.location.removeprefix("s3://").strip("/"))
        return DirectoryBucket(Path(self.location))

    def store(self, value: Any, asset: str, context: RunContext) -> Pointer:
        with tempfile.TemporaryDirectory() as staging:
            write_tree(value, Path(staging))
            publish_to_bucket(Path(staging), self._bucket())
        generated_at = value[meta_path().as_posix()]["generated_at"]
        return Pointer(asset, self.name, f"{self.location.rstrip('/')}/data/", {"generated_at": generated_at, "run_id": context.run_id})

    def load(self, pointer: Pointer) -> dict[str, bytes]:
        """Every published file's bytes, by path under `data/`: what parity compares."""
        bucket = self._bucket()
        return {key.removeprefix("data/"): bucket.get(key) for key in bucket.etags("data/")}

    def latest(self, asset: str, partition: str | None = None) -> Pointer | None:
        try:
            meta_file = json.loads(self._bucket().get(f"data/{meta_path().as_posix()}"))
        except (FileNotFoundError, KeyError, OSError):
            return None
        except Exception as error:  # S3's NoSuchKey
            if type(error).__name__ in ("NoSuchKey", "ClientError"):
                return None
            raise
        return Pointer(asset, self.name, f"{self.location.rstrip('/')}/data/", {"generated_at": meta_file["generated_at"]})

"""S3: fetching the build's inputs, and publishing a checked build to the site bucket (ADR 0004)."""

import hashlib
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config

from snacker.contract import meta_path

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

S3_SCHEME = "s3://"
DATA_PREFIX = "data/"
CONTENT_TYPE = "application/json"
CACHE_CONTROL = "max-age=60"
PARALLEL_REQUESTS = 64
"""How many objects are fetched or uploaded at once; the spike in aws-deployment ticket 01
found 64 about 5x faster than one at a time."""
DELETE_BATCH = 1000
"""The most keys one S3 DeleteObjects request takes."""


class Bucket(Protocol):
    """The few S3 operations the build needs, so tests can stand in a bucket of their own."""

    def etags(self, prefix: str) -> dict[str, str]:
        """Every key under `prefix`, with its ETag (no quotes)."""
        ...

    def modified(self, prefix: str, *, start_after: str = "") -> dict[str, datetime]:
        """Every key under `prefix` that sorts after `start_after`, with when it was last modified."""
        ...

    def get(self, key: str) -> bytes: ...

    def put(self, key: str, body: bytes, *, content_type: str, cache_control: str) -> None: ...

    def delete(self, keys: list[str]) -> None: ...


def s3_location(location: str) -> tuple[str, str] | None:
    """`s3://<bucket>/<key>` as (bucket, key), or None for any other location."""
    if not location.startswith(S3_SCHEME):
        return None
    bucket, _, key = location.removeprefix(S3_SCHEME).partition("/")
    return bucket, key


def fetch(location: str, local_dir: Path, open_bucket: Callable[[str], Bucket]) -> Path:
    """A local path to read an input from: a local path as it is, an s3:// object copied to
    `local_dir/<its name>`, or an s3:// prefix copied under `local_dir` with the layout below
    it kept (copying first is 5x faster than a direct glob over S3; aws-deployment ticket 01)."""
    if (s3 := s3_location(location)) is None:
        return Path(location)
    bucket_name, key = s3
    bucket = open_bucket(bucket_name)
    if key in bucket.etags(key):
        path = local_dir / PurePosixPath(key).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bucket.get(key))
        return path
    prefix = key.rstrip("/") + "/"

    def download(key: str) -> None:
        path = local_dir / key.removeprefix(prefix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bucket.get(key))

    # Nothing to copy means a wrong location, not a building with no scans: building from it
    # would publish an empty site over the real one.
    keys = list(bucket.etags(prefix))
    if not keys:
        raise FileNotFoundError(f"nothing in {location}")
    with ThreadPoolExecutor(PARALLEL_REQUESTS) as pool:
        list(pool.map(download, keys))
    return local_dir


@dataclass(frozen=True)
class Published:
    """What a publish changed in the site bucket."""

    uploaded: list[str]
    """Keys uploaded, data/meta.json last if it changed."""
    deleted: list[str]
    """data/ keys the build no longer writes."""


def publish_to_bucket(staging_dir: Path, bucket: Bucket) -> Published:
    """Bring the bucket's data/ in line with a checked build, touching nothing outside data/.

    Only files whose MD5 differs from the listed ETag are uploaded, which holds only with
    SSE-S3 and single-part uploads (ADR 0004). Keys the build no longer writes are deleted.
    meta.json goes last, so a page that sees the new build time also sees the new files.
    """
    listed = bucket.etags(DATA_PREFIX)
    built = {
        DATA_PREFIX + path.relative_to(staging_dir).as_posix(): path
        for path in sorted(p for p in staging_dir.rglob("*") if p.is_file())
    }
    changed = {
        key: body for key, path in built.items()
        if listed.get(key) != hashlib.md5(body := path.read_bytes()).hexdigest()
    }
    meta_key = DATA_PREFIX + meta_path().as_posix()
    meta = changed.pop(meta_key, None)

    def upload(key: str) -> None:
        bucket.put(key, changed[key], content_type=CONTENT_TYPE, cache_control=CACHE_CONTROL)

    with ThreadPoolExecutor(PARALLEL_REQUESTS) as pool:
        list(pool.map(upload, changed))
    stale = sorted(listed.keys() - built.keys())
    if stale:
        bucket.delete(stale)
    if meta is not None:
        bucket.put(meta_key, meta, content_type=CONTENT_TYPE, cache_control=CACHE_CONTROL)
    return Published(uploaded=[*changed, *([meta_key] if meta is not None else [])], deleted=stale)


S3_OPERATIONS: Counter[str] = Counter()
"""S3 requests made since the last `report_s3_operations`, by operation type."""


def report_s3_operations() -> dict[str, int]:
    """Print the S3 requests tallied since the last report, then start a new tally."""
    tally = dict(S3_OPERATIONS)
    total = sum(tally.values())
    by_type = "".join(f", {name} {count}" for name, count in sorted(tally.items()))
    print(f"S3 operations: {total} total{by_type}")
    S3_OPERATIONS.clear()
    return tally


def log_s3(operation: str, message: str) -> None:
    S3_OPERATIONS[operation] += 1
    print(f"S3 {operation} {message}")


class S3Bucket:
    """A Bucket on S3, with credentials from the standard AWS environment or profile."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.client: "S3Client" = boto3.client("s3", config=Config(max_pool_connections=PARALLEL_REQUESTS))

    def _list(self, prefix: str, start_after: str = "") -> list[dict]:
        where = f"s3://{self.name}/{prefix}" + (f" starting after {start_after}" if start_after else "")
        log_s3("LIST", f"prefix {prefix}" + (f", start-after {start_after}" if start_after else ""))
        items: list[dict] = []
        pages = 0
        for page in self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.name, Prefix=prefix, **({"StartAfter": start_after} if start_after else {})
        ):
            pages += 1
            items.extend(page.get("Contents", []))
        print(f"S3 LIST returned {len(items)} objects in {pages} pages from {where}")
        return items

    def etags(self, prefix: str) -> dict[str, str]:
        return {item["Key"]: item["ETag"].strip('"') for item in self._list(prefix)}

    def modified(self, prefix: str, *, start_after: str = "") -> dict[str, datetime]:
        return {item["Key"]: item["LastModified"] for item in self._list(prefix, start_after)}

    def get(self, key: str) -> bytes:
        body = self.client.get_object(Bucket=self.name, Key=key)["Body"].read()
        log_s3("GET", f"s3://{self.name}/{key} ({len(body)} bytes)")
        return body

    def put(self, key: str, body: bytes, *, content_type: str, cache_control: str) -> None:
        self.client.put_object(
            Bucket=self.name, Key=key, Body=body, ContentType=content_type, CacheControl=cache_control
        )
        S3_OPERATIONS["PUT"] += 1

    def delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), DELETE_BATCH):
            batch = keys[start:start + DELETE_BATCH]
            reply = self.client.delete_objects(
                Bucket=self.name, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True}
            )
            S3_OPERATIONS["DELETE"] += 1
            if errors := reply.get("Errors"):
                raise RuntimeError(f"s3://{self.name}: could not delete {errors}")


class DirectoryBucket:
    """A Bucket over a local directory, keyed by each file's path below it, for local runs."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _files(self, prefix: str) -> list[str]:
        if not self.root.is_dir():
            return []
        keys = (p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        return sorted(key for key in keys if key.startswith(prefix))

    def etags(self, prefix: str) -> dict[str, str]:
        return {key: hashlib.md5((self.root / key).read_bytes()).hexdigest() for key in self._files(prefix)}

    def modified(self, prefix: str, *, start_after: str = "") -> dict[str, datetime]:
        return {
            key: datetime.fromtimestamp((self.root / key).stat().st_mtime, UTC)
            for key in self._files(prefix) if key > start_after
        }

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def put(self, key: str, body: bytes, *, content_type: str, cache_control: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def delete(self, keys: list[str]) -> None:
        for key in keys:
            (self.root / key).unlink()

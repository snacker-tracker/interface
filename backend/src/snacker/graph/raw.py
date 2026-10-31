"""Where the raw scanner events are: a directory locally, the prod raw bucket when deployed."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RawFile:
    key: str
    """Relative to the raw root, e.g. `scans/2026/10/20/<name>`."""
    last_modified: datetime


class RawSource(Protocol):
    def list(self, folder: str, start_after: str = "") -> list[RawFile]:
        """The files under `folder` whose keys sort after `start_after`, in key order."""
        ...

    def read(self, key: str) -> bytes: ...


class LocalRaw:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def list(self, folder: str, start_after: str = "") -> list[RawFile]:
        base = self.root / folder
        if not base.is_dir():
            return []
        files = []
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            key = path.relative_to(self.root).as_posix()
            if key > start_after:
                files.append(RawFile(key, datetime.fromtimestamp(path.stat().st_mtime, UTC)))
        return files

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class S3Raw:
    """Read-only: keys under `prefix` in `bucket`."""

    def __init__(self, client: Any, bucket: str, prefix: str) -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix

    def list(self, folder: str, start_after: str = "") -> list[RawFile]:
        files = []
        arguments = {"Bucket": self.bucket, "Prefix": self.prefix + folder}
        if start_after:
            arguments["StartAfter"] = self.prefix + start_after
        for page in self.client.get_paginator("list_objects_v2").paginate(**arguments):
            for item in page.get("Contents", []):
                files.append(RawFile(item["Key"].removeprefix(self.prefix), item["LastModified"].astimezone(UTC)))
        return files

    def read(self, key: str) -> bytes:
        body: bytes = self.client.get_object(Bucket=self.bucket, Key=self.prefix + key)["Body"].read()
        return body


def raw_source(location: str) -> RawSource:
    """A directory, or `s3://bucket/prefix/`."""
    if location.startswith("s3://"):
        import boto3

        bucket, _, prefix = location.removeprefix("s3://").partition("/")
        return S3Raw(boto3.client("s3"), bucket, prefix if not prefix or prefix.endswith("/") else prefix + "/")
    return LocalRaw(location)

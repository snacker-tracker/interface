"""The raw scanner events, read incrementally by ADR 0011's watermark rule.

Raw events are files under `scans/` and `heartbeats/`, laid out by day (`<folder>/YYYY/MM/DD/…`)
as Firehose writes them, in a local directory or under an `s3://` prefix. A table built from them
keeps the newest last-modified time of any file it read: its watermark. A later read lists from
the day folder before the watermark, and reads only files modified after it, less a margin.
"""

import tempfile
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from snacker.storage import PARALLEL_REQUESTS, Bucket, DirectoryBucket, S3Bucket, s3_location

MARGIN = timedelta(minutes=15)
"""How far before the watermark a read goes again. Firehose names a file for its buffer's
start but writes it when the buffer closes, so a file can land after a later-named one."""

RAW_FILE_SCHEMA = pl.Schema({
    "raw_key": pl.String(),  # the raw file a row came from, relative to the raw root
    "source_last_modified": pl.Datetime("us", "UTC"),  # that file's last-modified time
})


@dataclass(frozen=True)
class RawEvents:
    """Where the raw events are: a bucket, and the key prefix (empty, or ending in /) of their root."""

    bucket: Bucket
    prefix: str = ""

    @classmethod
    def at(cls, location: str, open_bucket: Callable[[str], Bucket] = S3Bucket) -> "RawEvents":
        """A directory, or `s3://bucket/prefix/`."""
        s3 = s3_location(location)
        if s3 is None:
            return cls(DirectoryBucket(Path(location)))
        bucket, key = s3
        return cls(open_bucket(bucket), f"{key.rstrip('/')}/" if key else "")

    def since(self, folder: str, watermark: datetime | None) -> dict[str, datetime]:
        """The files under `folder` to read, by key relative to the root, with when each was last
        modified: every one without a `watermark`, else those modified after it less the margin."""
        root = f"{self.prefix}{folder}/"
        if watermark is None:
            listed = self.bucket.modified(root)
        else:
            day_before = (watermark - timedelta(days=1)).strftime("%Y/%m/%d/")
            listed = self.bucket.modified(root, start_after=root + day_before)
        return {
            key.removeprefix(self.prefix): modified
            for key, modified in listed.items()
            if watermark is None or modified > watermark - MARGIN
        }

    @contextmanager
    def downloaded(self, files: dict[str, datetime]) -> Iterator[Path]:
        """A temporary directory holding `files` under their keys, laid out like the raw root,
        which is what Snacker's normalisers read."""
        with tempfile.TemporaryDirectory(prefix="raw-") as scratch:
            local = Path(scratch)

            def download(key: str) -> None:
                path = local / key
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.bucket.get(self.prefix + key))

            with ThreadPoolExecutor(PARALLEL_REQUESTS) as pool:
                list(pool.map(download, files))
            yield local


def deliveries(local: Path, folder: str, files: dict[str, datetime]) -> pl.DataFrame:
    """Every envelope under `local/folder`, by event `id`, with the raw file it came in, in the order
    Snacker's normalisers read them (the same glob)."""
    by_path = pl.DataFrame(
        {
            "path": [str(local / key) for key in files],
            "raw_key": list(files),
            "source_last_modified": list(files.values()),
        },
        schema={"path": pl.String(), **RAW_FILE_SCHEMA},
    )
    return (
        pl.scan_ndjson(str(local / folder / "**" / "*"), schema={"id": pl.String()}, include_file_paths="path")
        .collect()
        .join(by_path, on="path", how="left", maintain_order="left")
        .select("id", "raw_key", "source_last_modified")
    )


def watermark(table: pl.LazyFrame | None) -> datetime | None:
    """The newest source last-modified time in a table built from raw files, if it has any rows."""
    if table is None:
        return None
    newest: datetime | None = table.select(pl.col("source_last_modified").max()).collect().item()
    return newest

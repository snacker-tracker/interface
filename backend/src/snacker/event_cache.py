"""The scans and heartbeats a build reads, through a cache of what earlier builds read (ADR 0011).

Legacy (#117): only the old build and extraction Lambdas use it. The graph's Delta tables, read by
the same watermark rule (`snacker.raw`), replace it; it's deleted at the switchover (#125).

Each cache is a Parquet file holding a normalised table, the code version that wrote it, and
a watermark: the newest LastModified of any raw file it has read. A later build reads only the
raw files modified since the watermark, less a margin, and merges them in. A cache that is
missing, or from another code version, is rebuilt from every raw file.
"""

import io
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from snacker.heartbeats import latest_heartbeats, normalise_heartbeats
from snacker.scans import normalise_scans
from snacker.storage import PARALLEL_REQUESTS, Bucket, DirectoryBucket, fetch, s3_location

MARGIN = timedelta(minutes=15)
"""How far before the watermark a build reads again. Firehose names a file for its buffer's
start but writes it when the buffer closes, so a file can land after a later-named one."""
PARQUET_CONTENT_TYPE = "application/vnd.apache.parquet"
VERSION_KEY = "snacker.code_version"
WATERMARK_KEY = "snacker.watermark"


@dataclass(frozen=True)
class Events:
    """What a build reads: every scan, and each scanner's heartbeats (at least its latest)."""

    scans: pl.DataFrame
    heartbeats: pl.DataFrame
    raw_files_read: int


@dataclass(frozen=True)
class Kind:
    """One kind of raw event: its folder under the raw prefix, how its files become rows,
    and how the cached rows and the newly read ones combine."""

    folder: str
    normalise: Callable[[Path], pl.DataFrame]
    merge: Callable[[pl.DataFrame], pl.DataFrame]


# Delivery is at-least-once and the margin reads files again, so a scan is one event id.
SCANS = Kind("scans", normalise_scans, lambda scans: scans.unique("event_id", keep="first", maintain_order=True))
# The scanners pages use only each scanner's latest heartbeat.
HEARTBEATS = Kind("heartbeats", normalise_heartbeats, latest_heartbeats)


@dataclass(frozen=True)
class Cached:
    table: pl.DataFrame
    watermark: datetime | None


def load_events(
    raw: str, *, cache: str | None, version: str | None, open_bucket: Callable[[str], Bucket], save: bool = True
) -> Events:
    """The scans and heartbeats in `raw` (a directory or an s3:// prefix).

    Without a `cache` (a directory or an s3:// prefix), every raw file is read. Without a
    `version`, every raw file is read and no cache written: the code can't say what wrote it.
    """
    if cache is None:
        with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
            raw_dir = fetch(raw, Path(scratch) / "raw", open_bucket)
            scans, heartbeats = normalise_scans(raw_dir), normalise_heartbeats(raw_dir)
        return Events(scans=scans, heartbeats=heartbeats, raw_files_read=-1)
    scans, scans_read = load(SCANS, raw, cache=cache, version=version, open_bucket=open_bucket, save=save)
    heartbeats, heartbeats_read = load(HEARTBEATS, raw, cache=cache, version=version, open_bucket=open_bucket, save=save)
    # The newest raw file is always within the margin, so a run that reads nothing found an
    # empty location: a wrong one, whose build would publish an empty site over the real one.
    if scans_read + heartbeats_read == 0:
        raise FileNotFoundError(f"nothing in {raw}")
    return Events(scans=scans, heartbeats=heartbeats, raw_files_read=scans_read + heartbeats_read)


def load_scans(
    raw: str, *, cache: str | None, version: str | None, open_bucket: Callable[[str], Bucket], save: bool = True
) -> pl.DataFrame:
    """Every scan in `raw`, as `load_events` reads them, without reading heartbeats."""
    if cache is None:
        with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
            return normalise_scans(fetch(raw, Path(scratch) / "raw", open_bucket))
    return load(SCANS, raw, cache=cache, version=version, open_bucket=open_bucket, save=save)[0]


def load(
    kind: Kind, raw: str, *, cache: str, version: str | None, open_bucket: Callable[[str], Bucket], save: bool
) -> tuple[pl.DataFrame, int]:
    """One kind's table, brought up to date from raw, and how many raw files that read."""
    raw_bucket, raw_prefix = located(raw, open_bucket)
    cache_bucket, cache_prefix = located(cache, open_bucket)
    cache_key = f"{cache_prefix}{kind.folder}.parquet"
    folder = f"{raw_prefix}{kind.folder}/"

    cached = read_cache(cache_bucket, cache_key, version) if version is not None else None
    if cached is None or cached.watermark is None:
        listed = raw_bucket.modified(folder)
        since = None
    else:
        day_before = (cached.watermark - timedelta(days=1)).strftime("%Y/%m/%d/")
        listed = raw_bucket.modified(folder, start_after=folder + day_before)
        since = cached.watermark - MARGIN
    to_read = {key: modified for key, modified in listed.items() if since is None or modified > since}

    with tempfile.TemporaryDirectory(prefix="snacker-") as scratch:
        local_dir = Path(scratch)

        def download(key: str) -> None:
            path = local_dir / key.removeprefix(raw_prefix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw_bucket.get(key))

        with ThreadPoolExecutor(PARALLEL_REQUESTS) as pool:
            list(pool.map(download, to_read))
        read = kind.normalise(local_dir)

    table = kind.merge(pl.concat([cached.table, read]) if cached is not None else read)
    watermark = max([*([cached.watermark] if cached and cached.watermark else []), *to_read.values()], default=None)
    changed = cached is None or watermark != cached.watermark or not table.equals(cached.table)
    if save and version is not None and changed:
        write_cache(cache_bucket, cache_key, table, version=version, watermark=watermark)
    return table, len(to_read)


def located(location: str, open_bucket: Callable[[str], Bucket]) -> tuple[Bucket, str]:
    """The bucket a location is in, and the key prefix (empty, or ending in /) it names."""
    s3 = s3_location(location)
    if s3 is None:
        return DirectoryBucket(Path(location)), ""
    bucket_name, key = s3
    return open_bucket(bucket_name), f"{key.rstrip('/')}/" if key else ""


def read_cache(bucket: Bucket, key: str, version: str) -> Cached | None:
    """The cache at `key`, if one is there and `version` wrote it."""
    # Listed first, as fetch does: the functions' roles may list but not see a missing key's 404.
    if key not in bucket.etags(key):
        return None
    body = bucket.get(key)
    metadata = pl.read_parquet_metadata(io.BytesIO(body))
    if metadata.get(VERSION_KEY) != version:
        return None
    watermark = metadata.get(WATERMARK_KEY)
    return Cached(
        table=pl.read_parquet(io.BytesIO(body)),
        watermark=datetime.fromisoformat(watermark) if watermark else None,
    )


def write_cache(bucket: Bucket, key: str, table: pl.DataFrame, *, version: str, watermark: datetime | None) -> None:
    body = io.BytesIO()
    metadata = {VERSION_KEY: version, **({WATERMARK_KEY: watermark.isoformat()} if watermark else {})}
    table.write_parquet(body, metadata=metadata)
    bucket.put(key, body.getvalue(), content_type=PARQUET_CONTENT_TYPE, cache_control="no-cache")

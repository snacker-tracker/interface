"""Publishing `site_tree`'s value, the whole site data tree (`snacker.sections`), with the diff-publish
of ADR 0004, to a directory locally or the shadow bucket in Lambda."""

import json
import tempfile
from pathlib import Path
from typing import Any

from snacker import sections
from snacker.contract import meta_path
from snacker.storage import Bucket, DirectoryBucket, S3Bucket, publish_to_bucket
from stepdag import Pointer, RunContext


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
            sections.write_tree(value, Path(staging))
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

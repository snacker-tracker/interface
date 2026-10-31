"""Where OpenFoodFacts's `food.parquet` comes from, and where copies of it go.

Hugging Face is read through the signed CDN URL its resolve URL redirects to: going through
`hf://` hits Hugging Face's rate limit partway through (Snacker's spike, GitHub issue #31).
"""

import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Protocol

HUGGING_FACE = "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet"


class Stream(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...

    def close(self) -> None: ...


class OpenFoodFactsSource(Protocol):
    def revision(self) -> str:
        """Changes whenever the file's content does."""
        ...

    def open(self) -> Stream: ...


class LocalFile:
    """A file on disk standing in for Hugging Face. Its revision is its size and modification time."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def revision(self) -> str:
        stat = self.path.stat()
        return f"local-{stat.st_size}-{stat.st_mtime_ns}"

    def open(self) -> Stream:
        return self.path.open("rb")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class HuggingFace:
    """OpenFoodFacts on Hugging Face. The revision is the file's LFS hash (`X-Linked-ETag`)."""

    def __init__(self, url: str = HUGGING_FACE, token: str | None = None) -> None:
        self.url = url
        self.token = token
        self._resolved: tuple[str, str] | None = None

    def _resolve(self) -> tuple[str, str]:
        """The signed CDN URL and the revision, from one HEAD request on the resolve URL."""
        if self._resolved is None:
            request = urllib.request.Request(self.url, method="HEAD")
            if self.token:
                request.add_header("Authorization", f"Bearer {self.token}")
            try:
                urllib.request.build_opener(_NoRedirect).open(request, timeout=30)
                raise RuntimeError(f"{self.url} didn't redirect to a CDN URL")
            except urllib.error.HTTPError as redirect:
                if redirect.code not in (301, 302, 303, 307, 308):
                    raise
                headers = redirect.headers
                revision = (headers.get("X-Linked-ETag") or headers.get("ETag") or headers.get("X-Repo-Commit") or "").strip('"')
                self._resolved = (headers["Location"], revision)
        return self._resolved

    def revision(self) -> str:
        return self._resolve()[1]

    def open(self) -> Stream:
        response: Stream = urllib.request.urlopen(self._resolve()[0], timeout=60)
        return response


def openfoodfacts_source(location: str) -> OpenFoodFactsSource:
    """`hf` for Hugging Face (token from `$HF_TOKEN`, if set), or a path to a local file."""
    if location == "hf":
        return HuggingFace(token=os.environ.get("HF_TOKEN"))
    return LocalFile(location)


class Files(Protocol):
    """Where large files are copied to: a directory locally, an S3 prefix in Lambda."""

    def upload(self, key: str, stream: Stream) -> tuple[str, int]:
        """Copy `stream` to `key` without holding it in memory or on local disk. Returns the URI and size.
        Nothing exists at `key` unless the whole stream was copied."""
        ...

    def exists(self, uri: str) -> bool:
        """Whether a copy is still there; the bucket's lifecycle rule expires old ones."""
        ...


class LocalFiles:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def upload(self, key: str, stream: Stream) -> tuple[str, int]:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".partial-", delete=False) as partial:
            try:
                shutil.copyfileobj(stream, partial, 8 * 1024 * 1024)
            except BaseException:
                Path(partial.name).unlink()
                raise
        Path(partial.name).replace(path)
        return path.resolve().as_uri(), path.stat().st_size

    def exists(self, uri: str) -> bool:
        return Path(uri.removeprefix("file://")).is_file()


class S3Files:
    """A multipart upload, streamed part by part. boto3 aborts the upload if the stream fails."""

    def __init__(self, client: Any, bucket: str, prefix: str) -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix

    def upload(self, key: str, stream: Stream) -> tuple[str, int]:
        from boto3.s3.transfer import TransferConfig

        full = self.prefix + key
        # 64 MB parts, read one at a time from the stream: a single stream, as the spec's first step.
        config = TransferConfig(multipart_chunksize=64 * 1024 * 1024, max_concurrency=4)
        self.client.upload_fileobj(stream, self.bucket, full, Config=config)
        size = int(self.client.head_object(Bucket=self.bucket, Key=full)["ContentLength"])
        return f"s3://{self.bucket}/{full}", size

    def exists(self, uri: str) -> bool:
        key = uri.removeprefix(f"s3://{self.bucket}/")
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError as error:
            if error.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise
        return True


def files_at(location: str) -> Files:
    """A directory, or `s3://bucket/prefix/`."""
    if location.startswith("s3://"):
        import boto3

        bucket, _, prefix = location.removeprefix("s3://").partition("/")
        return S3Files(boto3.client("s3"), bucket, prefix if not prefix or prefix.endswith("/") else prefix + "/")
    return LocalFiles(location)


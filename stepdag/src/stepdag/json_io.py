"""IO managers that keep values as JSON objects in a store: memory, a local directory, or S3."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from stepdag.io import Pointer, RunContext


class Store(Protocol):
    """A flat namespace of keys holding bytes."""

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes | None: ...

    def modified(self, prefix: str) -> dict[str, datetime]:
        """The keys under `prefix`, with when each was last written."""
        ...

    def uri(self, key: str) -> str: ...

    def key(self, uri: str) -> str: ...


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.written: dict[str, datetime] = {}

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data
        self.written[key] = datetime.now(UTC)

    def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def modified(self, prefix: str) -> dict[str, datetime]:
        return {k: t for k, t in self.written.items() if k.startswith(prefix)}

    def uri(self, key: str) -> str:
        return f"memory://{key}"

    def key(self, uri: str) -> str:
        return uri.removeprefix("memory://")


class DirectoryStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def put(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so a reader never sees half a file.
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(data)
        temporary.replace(path)

    def get(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.is_file() else None

    def modified(self, prefix: str) -> dict[str, datetime]:
        if not self.root.is_dir():
            return {}
        found = {
            p.relative_to(self.root).as_posix(): datetime.fromtimestamp(p.stat().st_mtime, UTC)
            for p in self.root.rglob("*")
            if p.is_file() and not p.name.startswith(".")
        }
        return {k: t for k, t in found.items() if k.startswith(prefix)}

    def uri(self, key: str) -> str:
        return (self.root / key).resolve().as_uri()

    def key(self, uri: str) -> str:
        return Path(unquote(urlparse(uri).path)).relative_to(self.root.resolve()).as_posix()


class S3Store:
    """Keys under `prefix` in an S3 bucket."""

    def __init__(self, client: Any, bucket: str, prefix: str = "") -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self.prefix + key, Body=data, ContentType="application/json")

    def get(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.prefix + key)
        except self.client.exceptions.NoSuchKey:
            return None
        body: bytes = response["Body"].read()
        return body

    def modified(self, prefix: str) -> dict[str, datetime]:
        found: dict[str, datetime] = {}
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix + prefix):
            found.update((item["Key"].removeprefix(self.prefix), item["LastModified"]) for item in page.get("Contents", []))
        return found

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{self.prefix}{key}"

    def key(self, uri: str) -> str:
        return uri.removeprefix(f"s3://{self.bucket}/{self.prefix}")


class _JsonIO:
    """Each materialization is one JSON object holding its value and its pointer."""

    name: str

    def __init__(self, store: Store, prefix: str = "") -> None:
        self.backend = store
        self.prefix = prefix

    def _write(self, key: str, value: Any, asset: str, context: RunContext) -> Pointer:
        pointer = Pointer(
            asset=asset,
            io_manager=self.name,
            uri=self.backend.uri(key),
            metadata={"run_id": context.run_id, "stored_at_ns": time.time_ns()},
        )
        self.backend.put(key, json.dumps({"pointer": pointer.to_json(), "value": value}).encode())
        return pointer

    def _read(self, key: str) -> dict[str, Any] | None:
        data = self.backend.get(key)
        return None if data is None else dict(json.loads(data))

    def load(self, pointer: Pointer) -> Any:
        stored = self._read(self.backend.key(pointer.uri))
        if stored is None:
            raise LookupError(f"{pointer.uri} doesn't exist")
        return stored["value"]


class RunJson(_JsonIO):
    """Keeps each run's materialization under the asset and the run's ID, so overlapping runs never
    share a key.

    `latest()` lists the asset's materializations and reads only the last written. S3 times writes
    to the second, so those written in the same second are all read and told apart by when each
    was stored.
    """

    name = "run_json"

    def store(self, value: Any, asset: str, context: RunContext) -> Pointer:
        return self._write(f"{self.prefix}runs/{asset}/{context.run_id}.json", value, asset, context)

    def latest(self, asset: str, partition: str | None = None) -> Pointer | None:
        written = self.backend.modified(f"{self.prefix}runs/{asset}/")
        if not written:
            return None
        last = max(written.values())
        pointers = [
            Pointer.from_json(stored["pointer"])
            for key, at in written.items()
            if at == last and (stored := self._read(key)) is not None
        ]
        return max(pointers, key=lambda p: int(p.metadata["stored_at_ns"]), default=None)


class FixedJson(_JsonIO):
    """Keeps an asset's materialization at one key, each run replacing the last."""

    name = "fixed_json"

    def _key(self, asset: str) -> str:
        return f"{self.prefix}fixed/{asset}.json"

    def store(self, value: Any, asset: str, context: RunContext) -> Pointer:
        return self._write(self._key(asset), value, asset, context)

    def latest(self, asset: str, partition: str | None = None) -> Pointer | None:
        stored = self._read(self._key(asset))
        return None if stored is None else Pointer.from_json(stored["pointer"])

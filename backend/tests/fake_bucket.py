"""An in-memory site or input bucket that records what was done to it."""

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class Put:
    key: str
    body: bytes
    content_type: str
    cache_control: str


@dataclass(frozen=True)
class Delete:
    keys: list[str]


@dataclass
class FakeBucket:
    objects: dict[str, bytes] = field(default_factory=dict)
    modified_at: dict[str, datetime] = field(default_factory=dict)
    """When each key was last modified; a key without an entry was modified at EPOCH."""
    calls: list[Put | Delete] = field(default_factory=list)
    gets: list[str] = field(default_factory=list)
    listings: list[tuple[str, str]] = field(default_factory=list)
    """(prefix, start_after) of each `modified` listing."""
    now: datetime = EPOCH
    """When a put modifies its key."""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def etags(self, prefix: str) -> dict[str, str]:
        return {key: hashlib.md5(body).hexdigest() for key, body in self.objects.items() if key.startswith(prefix)}

    def modified(self, prefix: str, *, start_after: str = "") -> dict[str, datetime]:
        self.listings.append((prefix, start_after))
        return {
            key: self.modified_at.get(key, EPOCH)
            for key in sorted(self.objects) if key.startswith(prefix) and key > start_after
        }

    def get(self, key: str) -> bytes:
        with self._lock:
            self.gets.append(key)
        return self.objects[key]

    def put(self, key: str, body: bytes, *, content_type: str, cache_control: str) -> None:
        with self._lock:
            self.calls.append(Put(key, body, content_type, cache_control))
            self.objects[key] = body
            self.modified_at[key] = self.now

    def delete(self, keys: list[str]) -> None:
        with self._lock:
            self.calls.append(Delete(keys))
            for key in keys:
                del self.objects[key]

    def puts(self) -> list[str]:
        return [call.key for call in self.calls if isinstance(call, Put)]

    def deletes(self) -> list[str]:
        return [key for call in self.calls if isinstance(call, Delete) for key in call.keys]


def opener(buckets: dict[str, FakeBucket]) -> Callable[[str], FakeBucket]:
    """Opens each bucket by name, as S3Bucket does."""
    return lambda name: buckets[name]

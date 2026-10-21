"""An in-memory site or input bucket that records what was done to it."""

import hashlib
import threading
from dataclasses import dataclass, field


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
    calls: list[Put | Delete] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def etags(self, prefix: str) -> dict[str, str]:
        return {key: hashlib.md5(body).hexdigest() for key, body in self.objects.items() if key.startswith(prefix)}

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def put(self, key: str, body: bytes, *, content_type: str, cache_control: str) -> None:
        with self._lock:
            self.calls.append(Put(key, body, content_type, cache_control))
            self.objects[key] = body

    def delete(self, keys: list[str]) -> None:
        with self._lock:
            self.calls.append(Delete(keys))
            for key in keys:
                del self.objects[key]

    def puts(self) -> list[str]:
        return [call.key for call in self.calls if isinstance(call, Put)]

    def deletes(self) -> list[str]:
        return [key for call in self.calls if isinstance(call, Delete) for key in call.keys]

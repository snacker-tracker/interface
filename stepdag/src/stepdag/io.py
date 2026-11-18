"""What crosses between steps, and what an asset's function sees of its run."""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Pointer:
    """Where one materialization is stored. Steps exchange pointers, never values."""

    asset: str
    io_manager: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"asset": self.asset, "io_manager": self.io_manager, "uri": self.uri, "metadata": self.metadata}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Pointer":
        return cls(data["asset"], data["io_manager"], data["uri"], dict(data.get("metadata", {})))


@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at: str
    asset: str
    config: dict[str, Any]
    """The run config shared by every asset."""
    asset_config: dict[str, Any]
    """The run config's section named after this asset, if any."""
    force: bool
    stamp: dict[str, Any] = field(default_factory=dict)
    """What this materialization was made from, filled in by the framework: `{"parents": {asset: pointer}}`.
    IO managers store it in the pointer's metadata under "stamp", so `latest()` returns it."""


class IOManager(Protocol):
    def store(self, value: Any, asset: str, context: RunContext) -> Pointer:
        """Store an asset's value, with the pointer `latest()` will return for it."""
        ...

    def load(self, pointer: Pointer) -> Any: ...

    def latest(self, asset: str, partition: str | None = None) -> Pointer | None: ...


@runtime_checkable
class Retaining(Protocol):
    """An IO manager that can drop an asset's older materializations, for an asset's retention setting."""

    def prune(self, asset: str, keep: int) -> None:
        """Remove all but the newest `keep` materializations of `asset`. Lineage is never removed."""
        ...


class _Unchanged:
    def __repr__(self) -> str:
        return "UNCHANGED"


UNCHANGED: Any = _Unchanged()
"""Returned by an asset's function to re-emit its latest materialization instead of storing a new one."""

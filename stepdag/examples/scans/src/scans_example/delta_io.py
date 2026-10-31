"""An IO manager that keeps each asset as a Delta table, with pointers pinned to a table version."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl
from deltalake import DeltaTable
from deltalake.exceptions import TableNotFoundError

from stepdag import Pointer, RunContext


@dataclass(frozen=True)
class Merge:
    """Upsert the asset's returned rows into its table, matching on `keys`.

    `update_when`, if given, is a predicate over the incoming row (`s`) and the table's (`t`),
    e.g. `"s.sent_at > t.sent_at"`: a matched row is replaced only when it holds.
    """

    keys: Sequence[str]
    update_when: str | None = None


class DeltaIO:
    """Each asset is the Delta table `<root>/<asset>`.

    `store` overwrites the table, or merges into it for assets bound to a `Merge` (except in a
    forced run, where the asset had no `previous` and returned the whole table). The pointer
    pins the version written, and `load` reads that version, so a step reads what its parent
    wrote even after later runs write again. Delta's own history holds each version's run, so
    `latest()` rebuilds the pointer from the table instead of from a separate record.
    """

    name = "delta"

    def __init__(self, root: str, merges: Mapping[str, Merge] | None = None, storage_options: dict[str, str] | None = None) -> None:
        self.root = root.rstrip("/")
        self.merges = dict(merges or {})
        self.storage_options = storage_options

    def _uri(self, asset: str) -> str:
        return f"{self.root}/{asset}"

    def _table(self, asset: str) -> DeltaTable | None:
        try:
            return DeltaTable(self._uri(asset), storage_options=self.storage_options)
        except TableNotFoundError:
            return None

    def store(self, value: Any, asset: str, context: RunContext) -> Pointer:
        if not isinstance(value, pl.DataFrame):
            raise TypeError(f"{asset}: the delta IO manager stores polars DataFrames, not {type(value).__name__}")
        # deltalake can't write dictionary-encoded columns, so Enums and Categoricals are stored as text.
        value = value.with_columns(pl.col(pl.Enum, pl.Categorical).cast(pl.String()))
        uri = self._uri(asset)
        metadata = {"stepdag_run_id": context.run_id}
        merge = self.merges.get(asset)
        # A forced run passes no `previous`, so a merging asset returns its whole table: replace it.
        if merge is None or context.force or self._table(asset) is None:
            # An overwrite replaces the schema too, so an asset can gain or lose columns.
            value.write_delta(
                uri,
                mode="overwrite",
                storage_options=self.storage_options,
                delta_write_options={"commit_properties": _commit(metadata), "schema_mode": "overwrite"},
            )
        else:
            predicate = " AND ".join(f"s.{k} = t.{k}" for k in merge.keys)
            (
                value.write_delta(
                    uri,
                    mode="merge",
                    storage_options=self.storage_options,
                    delta_merge_options={"predicate": predicate, "source_alias": "s", "target_alias": "t", "commit_properties": _commit(metadata)},
                )
                .when_matched_update_all(predicate=merge.update_when)
                .when_not_matched_insert_all()
                .execute()
            )
        table = self._table(asset)
        assert table is not None
        return self._pointer(asset, table.version(), context.run_id)

    def load(self, pointer: Pointer) -> pl.LazyFrame:
        return pl.scan_delta(pointer.uri, version=int(pointer.metadata["version"]), storage_options=self.storage_options)

    def latest(self, asset: str, partition: str | None = None) -> Pointer | None:
        table = self._table(asset)
        if table is None:
            return None
        version = table.version()
        history = table.history(1)
        run_id = history[0].get("stepdag_run_id") if history else None
        return self._pointer(asset, version, run_id)

    def _pointer(self, asset: str, version: int, run_id: str | None) -> Pointer:
        return Pointer(asset=asset, io_manager=self.name, uri=self._uri(asset), metadata={"version": version, "run_id": run_id})


def _commit(metadata: dict[str, str]) -> Any:
    from deltalake import CommitProperties

    return CommitProperties(custom_metadata=metadata)

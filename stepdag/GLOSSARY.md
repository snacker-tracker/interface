# stepdag

A framework that runs a graph of assets as a Step Functions workflow, one Lambda per asset, in the style of Dagster. Its decisions are in `docs/adr/` next to this file.

## Language

### Assets

**Asset**:
A named piece of data the graph produces, defined by a function that computes it from the assets it depends on.
_Avoid_: step, task, job, node (for the data rather than its place in the workflow)

**Parent**:
An asset that another asset depends on, and whose value it is computed from. An asset may be its own parent through its previous materialization.
_Avoid_: upstream, input, dependency (for the asset itself)

**Materialization**:
One stored result of an asset, produced by one run.
_Avoid_: output, version, snapshot

**Previous materialization**:
An asset's latest materialization, offered to its function when computing the next one, except in a forced run.
_Avoid_: last run, prior state

**Blocking check**:
A rule an asset's value must pass before it is stored. A failure fails the run, and the value is never stored.
_Avoid_: validation, test, assertion

### Storage

**Pointer**:
A small description of where one materialization is stored and what it was made from. Steps exchange pointers, never values.
_Avoid_: reference, handle, location, URI (for the whole description)

**IO manager**:
What stores an asset's value, loads it back from a pointer, and finds an asset's latest materialization. Which IO manager serves an asset depends on where the graph runs.
_Avoid_: storage backend, persister, adapter

**Skip**:
Re-emitting an asset's latest materialization instead of computing a new one, because its function says nothing has changed, it is outside the run's selection, or it has parents and its latest materialization was made by the same code from the parents' current latest ones and is within its max age, if it has one.
_Avoid_: cache hit, no-op

**Max age**:
How old an asset's latest materialization may be before the asset computes a new one even though it could skip because its parents are unchanged. An asset that depends on the clock, not only on its parents, declares one.
_Avoid_: TTL, expiry, staleness limit

### Runs

**Run**:
One execution of the graph, from its start to every asset having been materialized, skipped or failed.
_Avoid_: execution (except for Step Functions' own term), build, job

**Run config**:
Settings given to a run when it starts, shared by every asset, with an optional section for each asset.
_Avoid_: parameters, options, input

**Forced run**:
A run in which the selected assets skip nothing and start again from scratch, ignoring their previous materializations.
_Avoid_: full refresh, rebuild, backfill

**Selection**:
The assets a run is asked to materialize. Assets outside it re-emit their latest materialization.
_Avoid_: subset, filter, target

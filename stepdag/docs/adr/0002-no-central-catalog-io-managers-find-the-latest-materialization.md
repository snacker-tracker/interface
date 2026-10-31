# There is no central catalog: each IO manager finds its asset's latest materialization

Skipping, assets outside the selection, and `previous` all need an asset's latest materialization. stepdag keeps no record of materializations. Instead each IO manager answers `latest(asset, partition=None)`, next to `store` and `load`.

A pointer is `{asset, io_manager, uri, metadata}`. The IO manager supplies all of it, the metadata being its own (a row count, when it was written, a watermark). It must store the pointer with the value, so that `latest()` can return it.

When `latest()` finds nothing:
- `previous` is None;
- an asset that would have been skipped is computed instead;
- an asset outside the selection fails the run with an error naming it, rather than being computed when nobody asked for it.

## Considered options

- **A DynamoDB table of materializations.** It would give history and lineage, and a conditional write could refuse to record an older run's result over a newer one. Rejected as more than the framework needs: one more service for every deployment, and one more resource kind for an admin to create.
- **A `latest.json` per asset in S3,** written by stepdag. Rejected for the same reason: the IO manager already knows where its values are.

## Consequences

- **Overlapping runs are each IO manager's problem.** stepdag can't stop an older run's result from replacing a newer one's. An IO manager that cares has to guard its own writes, or accept that the next run corrects it.
- **No history.** Which run produced what is not recorded beyond what each pointer holds and the Step Functions execution history keeps.

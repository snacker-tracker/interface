# stepdag

Runs a graph of assets as a Step Functions workflow, one Lambda per asset. See `GLOSSARY.md` and `docs/adr/`.

## Skipping unchanged assets

Each run calls every selected asset's function, which returns `UNCHANGED` to re-emit its latest materialization (see ADR 0003). An asset with parents also skips without calling its function when its parents are unchanged (ADR 0006): its latest materialization records the pointer of each parent it was made from, and when those equal the parents' current latest pointers, the asset re-emits its latest and logs `(its parents are unchanged since it was made)`. A parent that failed in an earlier run is recomputed by the next one, so its children compute then too.

This is on by default. An asset with no parents never skips by this rule, and a forced run skips nothing. Turn it off for one asset with `@asset(..., skip_when_unchanged=False)` when its function depends on more than its parents, such as the clock or the config; the max age that ADR 0006 pairs with this is not built yet. A latest materialization written without a recorded stamp always computes. The stamp also records the code version: `$STEPDAG_CODE_VERSION` when set (Snacker's graph functions set it to the backend image digest), otherwise the git HEAD commit of the working directory, or none when the tree is dirty or git is unavailable. An asset skips only when its recorded code version equals the current one, so a new deploy computes every asset with parents once. A run's code version can be injected with `run(..., code_version=...)`.

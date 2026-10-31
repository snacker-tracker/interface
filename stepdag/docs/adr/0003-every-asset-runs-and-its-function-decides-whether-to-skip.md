# Every asset runs as a step, and its function decides whether to skip

The state machine is a static graph with no Choice states: every asset is a step in every run. A step that has nothing new to do re-emits its latest materialization's pointer, so the steps after it always get a pointer. A step skips when:
- **its function says so:** it returns "unchanged". The function knows what makes new work, for example a new key appearing in a parent that otherwise changes every run.
- **it is outside the run's selection.**

A forced run (`{"force": true}` in the run config) skips nothing, and gives every asset `previous=None`, so an asset that builds on its previous materialization starts again from scratch. With a selection, only the selected assets are forced. This is how a fix to an asset's code reaches results that would otherwise be skipped or built on. A deploy pipeline that starts a forced run after each deploy makes that automatic, and can leave out expensive assets by selection.

## Considered options

- **Skipping automatically on data and code versions,** Dagster-style. Each pointer would record its parents' data versions and the code version that made it. stepdag would skip when they match, and drop `previous` when the code differs. Deferred, not rejected: it's the subtlest part of the design, and nothing it saves is worth much yet. The two must come together, since skipping on data versions alone would keep skipping an asset after its code is fixed.
- **Conditions declared on the asset and evaluated before the step,** as a Choice state or a small check Lambda. Rejected: real conditions, such as "the copy is newer than the table", need IO anyway, and conditional branches make the state machine depend on the graph's logic.

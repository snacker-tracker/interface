# Assets with parents skip when their parents and code are unchanged

Every run used to compute every asset whose function didn't say "unchanged" ([ADR 0003](0003-every-asset-runs-and-its-function-decides-whether-to-skip.md)). A graph where one cheap source changes often (Snacker's heartbeats, every five minutes) and most of the work hangs off another that changes rarely (its scans, a handful a day) rebuilt everything downstream of the rare one on every run. This is the Dagster-style skipping ADR 0003 deferred, now decided.

An asset that has parents **skips** when all of these hold:
- **its parents are the ones it was made from:** its latest materialization's pointer records each parent's pointer, and they equal the parents' current latest pointers. A step that failed in an earlier run left its parents newer than the ones it recorded, so it computes in the next run instead of serving old output.
- **its code is the code that made it:** the pointer records the code version (the image digest in Lambda, the git commit in the CLI; a dirty tree never matches). Every deploy therefore recomputes these assets once, and no pipeline has to remember to force a run.
- **it is within its max age,** if it declares one: `max_age=seconds` on `@asset`.

The framework writes the recorded parents and code version into the pointer's metadata, next to what the IO manager supplies. A pointer without them means "compute".

The rule is on by default for an asset with parents. `skip_when_unchanged=False` turns it off. An asset with no parents is exempt, because "none of its parents changed" would hold forever: it keeps deciding for itself by returning "unchanged". There is no default max age. An asset that depends on the clock or on config, not only on its parents, must declare one; Snacker's five index sections that take the run's start time and `site_tree` declare 3 hours.

## Considered options

- **Opt in per asset.** Rejected: most assets are pure functions of their parents, so most would carry the annotation, and the asset that forgets it only costs money. The default errs the other way, and a missing max age on a clock-dependent asset is the risk accepted here.
- **Skip when no parent was recomputed in this run,** with flags passed between steps. Rejected: it can't see a step that failed earlier. If `code_pages` fails after `scanned` is recomputed, the next run finds `scanned` unchanged and would keep the old output until the next new scan, with no error.
- **A code version the developer bumps per asset,** or **a forced run after each deploy** (ADR 0003's remedy). Rejected: both rely on someone remembering. The image digest can't be forgotten, and the cost is one recompute per deploy.
- **A daily forced run, or a second scheduled forced run of the clock-dependent assets, to roll periods over.** Rejected: forcing re-reads every raw file and re-downloads the OpenFoodFacts copy, and a second scheduled run has to be kept in step with the first. A max age is per asset and independent of the schedule.
- **A Choice state or check Lambda that skips steps in the state machine.** Still rejected, for ADR 0003's reason. It also wouldn't be needed: the Lambdas still run every step, and re-emitting is cheap.

## Consequences

- The state machine is unchanged, so every run still has one transition per asset. This reduces Lambda time and storage writes, not Step Functions transitions.
- A Delta table's version moves on compaction, vacuum and checkpoint, so a parent can look changed when its data didn't. That recomputes unnecessarily and never serves stale output.
- Existing graphs change behaviour: their assets start skipping.
- Skipping re-emits the latest materialization, so retention and the latest-materialization lookups of [ADR 0002](0002-no-central-catalog-io-managers-find-the-latest-materialization.md) apply unchanged.

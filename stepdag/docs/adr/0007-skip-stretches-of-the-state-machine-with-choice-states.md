---
status: proposed
---

# Skip whole stretches of the state machine with Choice states (undecided)

**Not decided.** This records an idea and its trade-offs for later, so the discussion isn't lost. Revisit once [ADR 0006](0006-assets-with-parents-skip-when-their-parents-and-code-are-unchanged.md)'s rollout (#156) has real numbers.

ADR 0006 makes a step skip, but every step is still in the state machine. In Snacker's prod graph a run with nothing new is still about 17 Lambda invocations and about 20 billed Step Functions transitions, about $0.03 a day at around 49 runs a day. Only the shape of the state machine can avoid entering states, and the one state type that does that is a Choice. This reopens the "no Choice states" rule of [ADR 0003](0003-every-asset-runs-and-its-function-decides-whether-to-skip.md), for a condition the framework generates from the graph, not one an asset declares.

## What a Choice can do

- It compares values already in the state and goes to the `Next` of the first matching rule. It calls nothing, reads nothing, and is billed as a transition like any state.
- Every `Next` is fixed when the state machine is generated. A Choice inside a Parallel branch can only jump within that branch.
- A Parallel outputs a list of its branches' states, so a rule after one reads branches by position (`$[0]`, `$[1]`), which is fixed at generation. A missing path is a runtime error unless guarded with `IsPresent`.

## The shape being considered

Snacker's graph is two stretches that share a join. The sources are `scans`, `openfoodfacts_copy` and `heartbeats`. Behind the first two sits one chain (`products`, `scanned`, then a Parallel of nine sections that need only `scanned`). `scanners` joins `heartbeats` with `scanned`, and `site_tree` joins everything, so those two stay after the join, each guarded by its own Choice.

A Choice in front of the chain skips it when nothing in it would compute. Steps would add a `computed` flag per asset to the state they pass on, and skipped assets' latest pointers would be put in the state so the steps after them still get a pointer. A quiet run would be about 8 to 10 transitions and 6 to 8 invocations, against about 20 and 17 today (estimates, not measured). That is about $0.45 a month for Step Functions and Lambda together.

## Open question: where "would anything in the chain compute?" is decided

The answer has a part that depends on this run (did `scans` or `openfoodfacts_copy` compute?) and a part that doesn't (max age, a new code version, a stamp that doesn't match its parents because an earlier run failed, no materialization yet).

- **Forecast in `plan`.** `plan` already reads every asset's latest pointer and could compute the second part up front, so the Choice reads two booleans. No extra step. Against it: the skip rule is then evaluated twice, once in advance and once inside each step, so it must be one shared function. A forecast that wrongly says "nothing due" leaves a chain stale, silently.
- **A gate step just in time.** After the first level, a step runs the real rule on the real pointers for the next group, puts the skipped assets' pointers in the state, and a Choice reads the result. No forecasting. It costs one more invocation and one more transition per run (about $0.04 a month) and could reuse the `_plan` Lambda with a different input. This is the "check Lambda" ADR 0003 rejected, but that objection was to conditions each asset declares, which can need I/O of their own. This one is generic.
- **Do nothing.** Every step starts, decides, and re-emits. The simplest model, and what runs today. Costs the savings above.

## Alternatives that don't change the graph's shape

- **Express workflows for the 30-minute runs** bill per request and duration, not per transition, which would take the Step Functions bill to a few cents a month. They have a 5-minute limit and at-least-once starts, and the daily OpenFoodFacts download (339 s on 2026-11-15) would stay on Standard, so it means two state machines from one definition. Independent of this ADR, and can be combined with it.
- **A separate small state machine for heartbeat-only runs** saves about $0.40 a month, but two executions can then publish the site at once.

## What would settle it

- #156's measurement of the real saving from ADR 0006, and whether the remaining Step Functions cost matters to anyone.
- If it does: pick the gate over the forecast unless the extra step proves to matter, and write the "skipping a chain is always safe" tests first: a step that failed in an earlier run, a new code version, an expired max age, and a missing materialization, each with nothing new from the sources.

## Consequences if adopted

- The generated state machine is no longer one flat sequence of Parallel levels, so it is harder to read and to keep correct.
- A wrongly skipped chain is silent staleness, not an error, so the tests above are not optional.
- A skipped asset's step disappears from the execution history, so "why didn't X run?" is answered by the Choice's input, not by X's log line.

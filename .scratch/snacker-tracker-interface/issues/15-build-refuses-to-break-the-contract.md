# 15: The build refuses to publish output that breaks the contract

**What to build:** When `snacker build` finishes writing, it validates what it wrote against the schemas (ticket 13) and the layout and invariant check (ticket 14). If anything breaks the contract, the build exits non-zero and lists every violation by file, so a bad build never reaches the frontend silently. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output), 14 (Check the output's layout and invariants).

**Status:** ready-for-agent

- [ ] `snacker build` runs both checks over its output folder and fails with a readable list of violations when either fails.
- [ ] The checks are also available on their own (e.g. a `check` subcommand taking an output folder), for checking a tree built elsewhere.
- [ ] Whatever validates schemas at build time is a runtime dependency, or the schema check is done without one; decide and record which.
- [ ] A build test shows a contract violation stopping the build (e.g. by injecting a bad document).
- [ ] Run once against the real data: the build passes, and the time it adds is noted in the ticket comments.
- [ ] The backend README mentions the check.

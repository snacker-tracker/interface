# 15: The build refuses to publish output that breaks the contract

**What to build:** When `snacker build` finishes writing, it validates what it wrote against the schemas (ticket 13) and the layout and invariant check (ticket 14). If anything breaks the contract, the build exits non-zero and lists every violation by file, so a bad build never reaches the frontend silently. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output), 14 (Check the output's layout and invariants).

**Status:** resolved

- [x] `snacker build` runs both checks over its output folder and fails with a readable list of violations when either fails.
- [x] The checks are also available on their own (e.g. a `check` subcommand taking an output folder), for checking a tree built elsewhere.
- [x] Whatever validates schemas at build time is a runtime dependency, or the schema check is done without one; decide and record which.
- [x] A build test shows a contract violation stopping the build (e.g. by injecting a bad document).
- [x] Run once against the real data: the build passes, and the time it adds is noted in the ticket comments.
- [x] The backend README mentions the check.

## Comments

- 2026-10-19: Implemented.
  - **How a build publishes:** it writes into `<out>/.data-building/`, runs `contract_violations` there, and swaps it in for `<out>/data/` only if nothing is wrong.
    - **On a violation,** it raises `ContractBroken` with the list, and the previous `data/` is untouched. The CLI prints up to 50 violations and exits 1.
    - **A side effect:** a passing build now replaces `data/` entirely, so stale files from earlier builds no longer linger. Before, they would sit there and fail the layout check.
  - **`snacker check --out <dir>`** runs the check alone.
  - **Dependencies:** pydantic and jsonschema are now runtime dependencies. The check validates against the schema generated in memory from the contract, which a test keeps identical to the committed copy. types-jsonschema stays a dev dependency.
  - **Tests:**
    - A build whose summary loses an hour is refused, with one violation per code scans file.
    - The previous `meta.json` survives the refused build, and the staging folder is kept.
    - A rebuild drops files the new build doesn't write.
  - **Real data:** passes. The full CLI build went from about 4s to about 6s; the check alone takes about 2s. Running `check` on a tree with two hand-broken files listed both and exited 1.

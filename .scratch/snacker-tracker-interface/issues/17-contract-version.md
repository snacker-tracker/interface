# 17: A contract version, so the frontend notices mismatched data

**What to build:** `meta.json` carries a contract version, and the frontend knows which version it was built for. When the deployed data and the deployed interface are out of step, people see a clear message saying so instead of half-rendered pages. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output), 16 (Generate the frontend's data types from the schemas).

**Status:** resolved

- [x] The contract module defines a contract version; `meta.json` includes it as `contract_version`, and the meta schema requires it.
- [x] The version is a single integer bumped on any breaking change to the contract; the rule for when to bump is written next to it and in the PRD.
- [x] The frontend's expected version comes from the generated contract (not a second hand-typed constant).
- [x] When `meta.json`'s version differs from the expected one, every page shows a clear "data and interface are out of step" message with both versions, and the rest of the page doesn't attempt to render.
- [x] A build test asserts `contract_version` in `meta.json`.
- [x] Checked by building, then editing `meta.json` to a different version and loading a page.

## Comments

- 2026-10-19: Implemented.
  - **Backend:** the contract module defines `CONTRACT_VERSION = 1`, typed as `Literal[1]`, with the rule for when to bump it beside it. The rule is repeated in PRD §7.2. `meta.json` now includes `contract_version`, and the schema requires it as `const: 1`.
  - **Frontend:** the contract script generates `CONTRACT_VERSION` from that `const`, so there's no second hand-typed constant.
  - **The guard:** the layout waits for `meta.json` before rendering anything else. On a mismatch it shows only the title and an alert naming both versions; the location selector and scanners link are hidden too, so no other data file is fetched. Data built before versions existed reads as "none (built before versions)". If `meta.json` is missing or fails to load, pages render as before and report their own errors.
  - **Tests:** a build test checks `contract_version` in `meta.json`, and a schema test rejects version 2.
  - **Checked:**
    - Rendered under happy-dom (a throwaway harness of the app's SSR bundle, with fetch served from disk).
    - The old `public-data`, which had no version, showed the out-of-step message on every page.
    - After a rebuild, the index, code, scanners and top-unknown pages rendered with real data.
    - A copy with `contract_version: 2` showed the message naming 2 and 1.
    - Not checked in a real browser.

# 17: A contract version, so the frontend notices mismatched data

**What to build:** `meta.json` carries a contract version, and the frontend knows which version it was built for. When the deployed data and the deployed interface are out of step, people see a clear message saying so instead of half-rendered pages. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output), 16 (Generate the frontend's data types from the schemas).

**Status:** ready-for-agent

- [ ] The contract module defines a contract version; `meta.json` includes it as `contract_version`, and the meta schema requires it.
- [ ] The version is a single integer bumped on any breaking change to the contract; the rule for when to bump is written next to it and in the PRD.
- [ ] The frontend's expected version comes from the generated contract (not a second hand-typed constant).
- [ ] When `meta.json`'s version differs from the expected one, every page shows a clear "data and interface are out of step" message with both versions, and the rest of the page doesn't attempt to render.
- [ ] A build test asserts `contract_version` in `meta.json`.
- [ ] Checked by building, then editing `meta.json` to a different version and loading a page.

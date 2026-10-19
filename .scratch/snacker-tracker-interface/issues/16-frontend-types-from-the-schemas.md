# 16: Generate the frontend's data types from the schemas

**What to build:** The frontend stops keeping its own hand-written copy of the output shapes. Its data types are generated from the committed JSON Schemas (ticket 13), so a change to the contract shows up as a TypeScript error wherever the frontend relies on the old shape. Fetching and data-path code stay hand-written. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output).

**Status:** ready-for-agent

- [ ] An npm script generates the TypeScript types for every file document and shared row from the schemas; the generated file is committed and marked as generated.
- [ ] The frontend build (or lint) fails when the generated types are out of date with the schemas.
- [ ] The hand-written type definitions for the static JSON are removed; pages and components use the generated types, keeping the existing names (`ScanRow`, `IndexData`, …) or renaming consistently.
- [ ] The period list used for tabs still comes from one place and matches the schema's period keys.
- [ ] `tsc` passes, and the index, code and scanners pages render against a fresh build.

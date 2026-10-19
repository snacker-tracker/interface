# 16: Generate the frontend's data types from the schemas

**What to build:** The frontend stops keeping its own hand-written copy of the output shapes. Its data types are generated from the committed JSON Schemas (ticket 13), so a change to the contract shows up as a TypeScript error wherever the frontend relies on the old shape. Fetching and data-path code stay hand-written. Requested 2026-10-19.

**Blocked by:** 13 (Publish JSON Schemas for the output).

**Status:** resolved

- [x] An npm script generates the TypeScript types for every file document and shared row from the schemas; the generated file is committed and marked as generated.
- [x] The frontend build (or lint) fails when the generated types are out of date with the schemas.
- [x] The hand-written type definitions for the static JSON are removed; pages and components use the generated types, keeping the existing names (`ScanRow`, `IndexData`, …) or renaming consistently.
- [x] The period list used for tabs still comes from one place and matches the schema's period keys.
- [x] `tsc` passes, and the index, code and scanners pages render against a fresh build.

## Comments

- 2026-10-19: Implemented.
  - **Generation:** `npm run contract` (`frontend/scripts/contract.mjs`) compiles the schema with json-schema-to-typescript into `src/contract.ts`, which is committed and marked as generated. The script:
    - strips the schema's empty root type and the boilerplate comments
    - keeps only the reference where a `$ref` has a description beside it, which would otherwise produce a duplicate `TopScansByPeriod1`
    - generates `PERIODS` and `Period` from the schema's period keys, so the tabs and the contract share one list
  - **Staleness check:** `npm run contract:check` runs at the start of `build` and `lint`. Appending a line to `contract.ts` made `npm run build` exit 1.
  - **Type names:** the hand-written types are gone from `data.ts`, which now only holds paths and fetching. Components import their types from `contract.ts`, and the file types are renamed to match the backend: `IndexData` → `IndexFile`, `CodeScansData` → `CodeScansFile`, and likewise for Product, Scanners, Meta and Locations.
  - **Checked:**
    - `tsc` and the build pass, and oxlint is clean.
    - The real-data build was republished to `public-data/`.
    - Pages were **not** rendered in a browser: the bundled headless Chromium lacks system libraries, and happy-dom can't parse the production bundle. Instead, I built the frontend unminified before and after this change. The two bundles are identical except for where `PERIODS` sits, so runtime behaviour is unchanged.

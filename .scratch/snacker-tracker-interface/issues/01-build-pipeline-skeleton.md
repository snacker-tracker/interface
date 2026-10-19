# 01: Build pipeline skeleton: all-locations index JSON

**What to build:** A maintainer can run one build command against the raw scan data and get the index data for the `all` location as a static JSON file: daily scan counts across all history, plus the 25 most recent scans. They can check the result by opening the output locally. This ticket sets up the backend (uv, Polars, pytest) and the end-to-end build test seam that later tickets extend. See the spec and the PRD (R1, §7) for the scan model and data contract.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The repo ignores the raw data folder and the generated output folder in git.
- [x] The backend is a uv-managed Python project using Polars, with a CLI entry point that runs the build with explicit input and output locations.
- [x] Scan files that hold one or more events, one JSON envelope per line, are parsed, in both the backfill format (`/scans`, `from-backup`, device `scanned_at`) and the live format (`scans`, `scanner`, no `scanned_at`).
- [x] Each scan is normalised to event ID, code (always a string), location, `scanned_at` in UTC, `scanned_at_source` (`device` or `reported`) and `origin` (`backfill` or `live`). `scanned_at` falls back to the envelope `time`.
- [x] Duplicate event IDs are counted once.
- [x] The build writes a meta file with an injected build time, and an index file for `all` with daily `{date, count}` entries and the 25 most recent scan rows, newest first. Days are bucketed in UTC for now; ticket 04 switches this to local time. Days with no scans are left out.
- [x] Each normalisation and aggregation step is a clearly named function with explicit inputs and outputs, so it can be lifted into Dagster later.
- [x] End-to-end tests (seam 1) use small fixture files in the real envelope formats, run the build into a temporary folder, and assert on the files written and their JSON. They cover both eras, the timestamp fallback, multi-event files, duplicates, daily counts, and the order and size of the recent list.
- [x] Running the build against the real local data finishes and produces a plausible index file (about 8,084 scans in total).

## Comments

- 2026-10-19: Implemented. The build seam has 7 end-to-end tests: both eras, the timestamp fallback, multi-event files, redelivered duplicates, daily counts, the recent list, and build failure on an unknown `source` or a timestamp without a timezone. Against the real data the build writes 8,084 scans across 396 days. Review follow-ups applied: strict input validation, one shared timestamp format, and the module renamed to `index_page`. Days are still bucketed in UTC until ticket 04.

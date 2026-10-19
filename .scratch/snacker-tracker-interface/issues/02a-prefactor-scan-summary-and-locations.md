# 02a: Prefactor: Scan summary and Locations modules

**What to build:** A refactor with no change in behaviour, so tickets 03, 04 and 06 each change one module instead of spreading across the build. The build output stays byte-for-byte identical. Two deep modules get their own test seams, agreed in the architecture review on 2026-10-19 (candidates 1 and 2). Terms are as defined in GLOSSARY.md.

- **Scan summary** replaces the page-named index module.
  - Its interface takes a scans table that carries each scan's office time zone, plus the recent-list size (25).
  - It returns a small typed summary already shaped like the PRD's JSON: daily counts by local date, and the most recent scan rows, newest first.
  - It owns the shape of a scan row and the date and timestamp formatting.
  - Hourly counts are not added here; ticket 06 adds them.
- **Locations** is built once from the scans.
  - It answers which locations are selectable (only `all` for now) and which scans fall within a location (all of them, for `all`).
  - It attaches each scan's office time zone (`UTC` for every scan, for now).
- **The build** asks Locations to attach time zones once. Then, for each selectable location, it summarises the scans within that location and writes the index file.

**Blocked by:** 02 (Index page).

**Status:** resolved

- [x] A Scan summary module exists with the interface above, and the old index module is gone.
- [x] A Locations module exists with the interface above (built from scans; selectable, within, time zones).
- [x] The build uses both modules, and running it against the real data produces output identical to before, apart from `generated_at`.
- [x] The daily-count and recent-list tests move from the build seam to the Scan summary seam (replaced, not duplicated). They include a scan near local midnight in a non-UTC time zone, to prove bucketing follows the time zone column.
- [x] Location tests cover the current behaviour (`all` is the only selectable location, `within("all")` returns every scan, a location that isn't selectable is refused, every scan gets `UTC`).
- [x] The build tests keep meta, normalisation (both eras, the timestamp fallback, duplicates, failing on bad input) and the file contract.

## Comments

- 2026-10-19: Implemented. The `scan_summary` module provides `summarise(scans, recent_limit=)`, returning a `ScanSummary` with `daily` and `recent`. The `locations` module provides `Locations.from_scans(...)` with `.selectable()`, `.within()` and `.with_office_time_zones()`. Names follow GLOSSARY.md; the zone column is `office_time_zone`. There are 4 tests at the Scan summary seam, including a Bangkok-midnight case, and 4 at the Locations seam. The build seam keeps 6 tests, with its daily and recent tests moved rather than duplicated. A build against the real data gives an `all.json` identical to the pre-refactor output. Review follow-ups applied: glossary-aligned names, OpenFoodFacts removed from the glossary, private helpers, a test for refusing a non-selectable location, and the wording of tickets 04 and 06.

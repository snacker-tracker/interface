# 14: Check the output's layout and invariants

**What to build:** A check over a whole built output folder for the parts of the contract a schema can't express: which files must exist, and the rules that hold across fields and files. It reports every violation with the file it's in. The fixture build passes it, and deliberately broken trees fail it. Requested 2026-10-19.

**Blocked by:** 12 (Gather the output contract into one backend module).

**Status:** resolved

- [x] **Layout:** `meta.json` and `locations.json` exist; an index file and a scanners file exist for every selectable location (including `all`); a product file exists for every code that appears in any scan row or top-scans list; a code's per-location scans file exists only for selectable locations; no other files are present.
- [x] **Cross-file:** every location named in a file is a selectable location, and every code in a scan row has a product file.
- [x] **Hourly:** exactly 24 entries, hours 0-23 in order.
- [x] **Daily:** dates ascending, unique, no zero counts.
- [x] **Recent:** newest first, at most the configured recent-list size.
- [x] **Top scans:** all eight periods present in both `top_scans` and `top_unknown_scans`; each list at most the configured size, counts non-increasing; shares in (0, 1] and summing to at most 1 per list; unknown-only lists hold only rows with `known` false.
- [x] **Times:** `scanned_at`, `last_seen` and `generated_at` are UTC with a `Z`; a scan row's `office_time` is the same instant as its `scanned_at`, with the offset of its `office_time_zone`.
- [x] Tests: the fixture build passes; a tree with each kind of violation (a missing index file, a 23-entry hourly, an unknown location, mismatched office time) fails with a message naming the file.
- [x] PRD §7.1 states the layout and invariants as the contract.

## Comments

- 2026-10-19: Implemented.
  - `check.contract_violations(data_dir)` now covers all three layers:
    - **Shape:** the schema, as in ticket 13.
    - **Layout:** the required files exist, each file sits at the path its own `code` and `location` give (this also pins the encoding), and nothing else is written.
    - **Invariants:** every rule in this ticket, plus a few found while writing it:
      - In a code scans file, `hourly` and `daily` have the same total, which isn't zero.
      - `recent` holds exactly `min(total, limit)` rows.
      - A code appears at most once in each top list.
      - Every scanned code has a scans file for `all`.
      - Rows and scanners are within their file's location.
      - Scanners are unique and ordered by name.
  - **Changes to the plan:**
    - A **scanner's location** only has to be within its file's location, not selectable. A scanner that has sent heartbeats but no scans can be at a location that no scan names.
    - **Shares** may add up to just over 1, because each is rounded to 4 places. The tolerance is 0.00005 per row.
  - Files that fail their schema are left out of the later checks, so one bad file doesn't cause a crash or a pile of follow-on violations.
  - The new PRD §7.4 lists the rules, and §7.1 now states the file rules in full.
  - **Tests:** the fixture build passes the check. There are 13 deliberate breakages, each reported with the file it's in.
  - **Real data:** 3,466 files, no violations.

# 14: Check the output's layout and invariants

**What to build:** A check over a whole built output folder for the parts of the contract a schema can't express: which files must exist, and the rules that hold across fields and files. It reports every violation with the file it's in. The fixture build passes it, and deliberately broken trees fail it. Requested 2026-10-19.

**Blocked by:** 12 (Gather the output contract into one backend module).

**Status:** ready-for-agent

- [ ] **Layout:** `meta.json` and `locations.json` exist; an index file and a scanners file exist for every selectable location (including `all`); a product file exists for every code that appears in any scan row or top-scans list; a code's per-location scans file exists only for selectable locations; no other files are present.
- [ ] **Cross-file:** every location named in a file is a selectable location, and every code in a scan row has a product file.
- [ ] **Hourly:** exactly 24 entries, hours 0-23 in order.
- [ ] **Daily:** dates ascending, unique, no zero counts.
- [ ] **Recent:** newest first, at most the configured recent-list size.
- [ ] **Top scans:** all eight periods present in both `top_scans` and `top_unknown_scans`; each list at most the configured size, counts non-increasing; shares in (0, 1] and summing to at most 1 per list; unknown-only lists hold only rows with `known` false.
- [ ] **Times:** `scanned_at`, `last_seen` and `generated_at` are UTC with a `Z`; a scan row's `office_time` is the same instant as its `scanned_at`, with the offset of its `office_time_zone`.
- [ ] Tests: the fixture build passes; a tree with each kind of violation (a missing index file, a 23-entry hourly, an unknown location, mismatched office time) fails with a message naming the file.
- [ ] PRD §7.1 states the layout and invariants as the contract.

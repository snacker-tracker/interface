# 10: Scanners page

**What to build:** A maintainer opens `/scanners` and sees every known scanner within the selected location: whether it is offline, its name and location, when it last sent a heartbeat, its last scan (what it scanned, and when) and its app version. The header's per-scanner list is replaced by one "Scanners" link that warns when any scanner there is offline. Terms (Scanner, Offline, Heartbeat, Scan, Location) are as defined in GLOSSARY.md; how scans are tied to scanners is in docs/adr/0002. Decided in a grilling session on 2026-10-19.

**Blocked by:** None (08 is done).

**Status:** resolved

- [x] Heartbeats and live scans keep their API key through normalisation. Backfill scans have none.
- [x] Each scanner entry in `scanners/by-location/{location}.json` gains `last_scan`: `{scanned_at, code, product_name}` for the latest scan sent with the scanner's API key, or null when there is none. `product_name` is null for an unknown product.
- [x] `/scanners` lists the scanners within the selected `?location=` (`all` shows every one), offline scanners first, then by name.
- [x] Each row shows:
  - status: ✓ Online / ✕ Offline, with icon and label; offline means no heartbeat for over an hour, and scans don't count,
  - name,
  - location,
  - last heartbeat as "X ago", with the exact time,
  - last scan as "X ago", with the product or code linking to its code page (keeping `?location`), or "Never",
  - app version.
- [x] A location with no scanners says so; a missing or failed file says scanner status is unavailable.
- [x] The header's per-scanner list and build time are replaced by one link to `/scanners` (keeping `?location`). It reads "Scanners", or "✕ N offline" when any scanner in the selected location is offline. The page shows when the data was built.
- [x] Build tests cover:
  - the last scan matched by API key,
  - a scanner with no scans,
  - backfill scans never matching,
  - two scanners with different keys.

## Comments

- 2026-10-19: Implemented.
  - **Backend:** scans and heartbeats keep their API key, and `scanner_statuses` adds each scanner's `last_scan` (the latest scan with the key from its latest heartbeat). docs/adr/0002 records the rule that each scanner has its own key.
  - **Header:** the old widget is replaced by `ScannersLink`, reading "Scanners" or "✕ N offline".
  - **Page:** `/scanners` lists scanners offline first, then by name, with status, name, location, last heartbeat (and its exact time), last scan (linking to its code page) or "Never", and version. It shows the data build time.
  - **Shared helpers:** time.ts, scanners.ts, Ago and ScannerStateLabel.
  - **Docs:** the glossary gains **Offline** and an extended **Scanner**; PRD G3 is updated.
  - **Tests:** the last scan by key, a scanner with no scans, backfill never matching, two keys, and a heartbeat with no key.
  - **Real data:** rpi-pico-w-01's last scan is 2026-10-16T10:33:45Z.
  - **Checked:** rendered in happy-dom (online, offline after 2h, no scanners, an unknown location). Not seen in a real browser.

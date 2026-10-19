# 08: Scanner status widget

**What to build:** A maintainer sees, in the header of every page, each scanner within the selected location: its name, how long ago it last sent a heartbeat, and its app version. A scanner is flagged offline after more than one hour without a heartbeat. The widget also shows when the data was built, so stale data can be told apart from a dead scanner. See PRD R6 and G3.

**Blocked by:** 03 (Location hierarchy and selector).

**Status:** resolved

- [x] Heartbeats are parsed and normalised in all three payload shapes (unversioned flat, unversioned flat with telemetry, `schema_version` 2 nested) to device name, location, app version and last-seen time.
- [x] For each selectable location, the build writes a scanners file listing every scanner within that location (hierarchy rules apply) with its latest last-seen time and the app version from its most recent heartbeat.
- [x] The header widget shows each scanner's name, "last seen X ago" (computed in the browser), app version, and an offline indicator when the last heartbeat is more than one hour old.
- [x] The widget shows the data build time from the meta file.
- [x] A location with no scanners shows an empty state, not an error.
- [x] End-to-end build tests cover all three heartbeat shapes, picking the latest heartbeat for each scanner, and grouping under parent locations and `all`.

## Comments

- 2026-10-19: Implemented.
  - **Heartbeats:** `heartbeats.py` normalises all three payload shapes to scanner, location, app version and sent time; an unknown shape stops the build. `read_events` moved to `events.py`, shared by scans and heartbeats.
  - **Scanner status:** taken from each scanner's latest heartbeat. The build writes `scanners/by-location/{location}.json` for each selectable location via `Locations.within`, so parent locations and `all` include the scanners beneath them. The JSON field is `name`, not `device_name`, per GLOSSARY "Scanner"; PRD §7.2 is updated.
  - **Header widget:**
    - ✓ Online / ✕ Offline, with icon and label, the status colour on the icon only for contrast; offline after more than an hour without a heartbeat,
    - the scanner name, "seen X ago" and the app version,
    - "Data built X ago (date, time)",
    - "No scanners here" for an empty location; "Scanner status unavailable" when the file is missing or fails to load,
    - refreshed every minute.
  - **Real data:** ~11k heartbeats parse; rpi-pico-w-01 shows v0.1.42, last seen 2026-10-19T09:45:47Z.
  - **Checked:** the widget was rendered in happy-dom at simulated times. It hasn't been seen in a real browser.

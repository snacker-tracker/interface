# 08: Scanner status widget

**What to build:** A maintainer sees, in the header of every page, each scanner within the selected location: its name, how long ago it last sent a heartbeat, and its app version. A scanner is flagged offline after more than one hour without a heartbeat. The widget also shows when the data was built, so stale data can be told apart from a dead scanner. See PRD R6 and G3.

**Blocked by:** 03 (Location hierarchy and selector).

**Status:** ready-for-agent

- [ ] Heartbeats are parsed and normalised in all three payload shapes (unversioned flat, unversioned flat with telemetry, `schema_version` 2 nested) to device name, location, app version and last-seen time.
- [ ] For each selectable location, the build writes a scanners file listing every scanner within that location (hierarchy rules apply) with its latest last-seen time and the app version from its most recent heartbeat.
- [ ] The header widget shows each scanner's name, "last seen X ago" (computed in the browser), app version, and an offline indicator when the last heartbeat is more than one hour old.
- [ ] The widget shows the data build time from the meta file.
- [ ] A location with no scanners shows an empty state, not an error.
- [ ] End-to-end build tests cover all three heartbeat shapes, picking the latest heartbeat for each scanner, and grouping under parent locations and `all`.

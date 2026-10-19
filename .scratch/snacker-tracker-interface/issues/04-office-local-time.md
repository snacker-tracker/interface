# 04: Office local time

**What to build:** Scans are counted per day in each office's local time, and scan times are shown in local time with the time zone indicated. A 9am Bangkok snack shows as 9am. A location with no configured time zone stops the build instead of silently producing wrong charts. See PRD R4.

**Blocked by:** 02 (Index page), 02a (Prefactor: Scan summary and Locations).

**Status:** ready-for-agent

- [ ] Locations (02a) takes the zone map and attaches each scan's real office time zone in place of `UTC`. Scan summary's bucketing already follows that column; its tests gain mixed-zone cases. Scan summary is also where scan rows gain their local time and time zone. Prefix-resolution and unmapped-location tests sit at the Locations seam.
- [ ] Backend config holds a map from location prefix to IANA time zone (initially `thailand` → `Asia/Bangkok`). The longest matching prefix wins.
- [ ] The build fails with a clear error naming any location with no matching time zone.
- [ ] Daily buckets use each scan's own local date. For `all`, and for parents spanning several time zones, each scan is bucketed in its own office's time zone.
- [ ] Scan rows carry the UTC timestamp, the local time and the time zone.
- [ ] The UI shows scan times in local time with the time zone indicated.
- [ ] End-to-end build tests cover scans just either side of UTC midnight and local midnight, mixed time zones under `all`, longest-prefix resolution, and the unmapped-location failure.

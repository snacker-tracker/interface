# 04: Office local time

**What to build:** Scans are counted per day in each office's local time, and scan times are shown in local time with the time zone indicated. A 9am Bangkok snack shows as 9am. A location with no configured time zone stops the build instead of silently producing wrong charts. See PRD R4.

**Blocked by:** 02 (Index page), 02a (Prefactor: Scan summary and Locations).

**Status:** resolved

- [x] Locations (02a) takes the zone map and attaches each scan's real office time zone in place of `UTC`. Scan summary's bucketing already follows that column; its tests gain mixed-zone cases. Scan summary is also where scan rows gain their local time and time zone. Prefix-resolution and unmapped-location tests sit at the Locations seam.
- [x] Backend config holds a map from location prefix to IANA time zone (initially `thailand` → `Asia/Bangkok`). The longest matching prefix wins.
- [x] The build fails with a clear error naming any location with no matching time zone.
- [x] Daily buckets use each scan's own local date. For `all`, and for parents spanning several time zones, each scan is bucketed in its own office's time zone.
- [x] Scan rows carry the UTC timestamp, the local time and the time zone.
- [x] The UI shows scan times in local time with the time zone indicated.
- [x] End-to-end build tests cover scans just either side of UTC midnight and local midnight, mixed time zones under `all`, longest-prefix resolution, and the unmapped-location failure.

## Comments

- 2026-10-19: Implemented.
  - **Config:** `config.py` holds `OFFICE_TIME_ZONES` (`thailand` → `Asia/Bangkok`).
  - **Locations:** each location resolves to its longest whole-segment prefix. An unmapped location, or an unknown zone name, fails when Locations is built, and so fails the build.
  - **Scan summary:** buckets each scan in its own office time zone, and rows gain `office_time` (ISO with offset) and `office_time_zone`. The names follow GLOSSARY.md (**Office time**, **Office time zone**); PRD R4 and §7.2 are updated to match.
  - **Tests:** prefix resolution and failures sit at the Locations seam. Scan summary covers the Bangkok-midnight boundary (16:59:59Z vs 17:00:00Z) and a Bangkok/London mixed case. The build seam has a next-day case and the unmapped failure.
  - **UI:** the scan list shows e.g. "16 Oct 2026, 17:33 GMT+7", with UTC and the zone name on hover.
  - **Real data:** 8,084 scans in total; 8 days' counts shift from UTC to Bangkok days.

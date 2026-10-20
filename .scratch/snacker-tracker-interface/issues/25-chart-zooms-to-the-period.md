# 25: The chart zooms to the period

**What to build:** Scans per day on the index page zooms to the selected period. Its detail view shows the period's days, and the brush on the all-history overview is placed on them, so the chart, Top scans and the healthiest and least healthy products all show the same span. Requested 2026-10-20.

**Blocked by:** 24 (One period selector for the index page).

**Status:** ready-for-agent

Decisions from the design session:

- **Days:** the zoom spans the office days the period touches, from its first day to the day the data was built.
  - Rolling periods include their partial first day, so "Last 7 days" shows 8 bars.
  - All time shows the whole history.
  - When the selected location spans offices in several time zones, the zoom starts at the earliest office day the period touches.
- **Where the days come from:** index files carry, for each period, its first and last office day. The browser has neither the build's office time zones nor a reliable "today" for them, and the backend already works these days out for the period lists.
  - All time's first day is the first scanned day, or none when nothing was scanned.
- **Brush:** brushing the overview by hand still works but doesn't change `?period=`. Choosing a period again moves the zoom back.
- **Heading and hint:** the heading stays "Scans per day", since a hand-brushed zoom can leave the period. The hint becomes "Zoomed to the period; drag across the lower chart to look elsewhere."
- **Empty days:** a period without scans still zooms to its days, so e.g. Today shows an empty day.
- **Contract:** still version 3, as long as version 3 hasn't been deployed. Otherwise it's bumped to 4.

- [ ] Index files carry each period's first and last office day. The schema, the generated frontend types and the check cover them.
- [ ] The check enforces that the first day is no later than the last, that the last is the build's office day, and that all time starts at the first scanned day.
- [ ] Build tests cover:
  - a calendar period
  - a rolling period with its partial first day
  - all time
  - a location with no scans in the period
- [ ] Scans per day zooms its detail view to the selected period and places the overview's brush on it. Brushing by hand still works.
- [ ] The real data builds and the check passes.
- [ ] The PRD (§6.2 I1, §7) describes the zoom and the new field.

## Comments

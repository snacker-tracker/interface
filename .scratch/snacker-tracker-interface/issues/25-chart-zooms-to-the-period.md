# 25: The chart zooms to the period

**What to build:** Scans per day on the index page zooms to the selected period. Its detail view shows the period's days, and the brush on the all-history overview is placed on them, so the chart, Top scans and the healthiest and least healthy products all show the same span. Requested 2026-10-20.

**Blocked by:** 24 (One period selector for the index page).

**Status:** resolved

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

- [x] Index files carry each period's first and last office day. The schema, the generated frontend types and the check cover them.
- [x] The check enforces that the first day is no later than the last, that the last is the build's office day, and that all time starts at the first scanned day.
- [x] Build tests cover:
  - a calendar period
  - a rolling period with its partial first day
  - all time
  - a location with no scans in the period
- [x] Scans per day zooms its detail view to the selected period and places the overview's brush on it. Brushing by hand still works.
- [x] The real data builds and the check passes.
- [x] The PRD (§6.2 I1, §7) describes the zoom and the new field.

## Comments

- 2026-10-20: Implemented.
  - **Backend:** index files gain `period_days`, which gives each period's `first_day` and `last_day` as office dates.
    - The days are computed in the location's scans' office time zones: the earliest first day and the latest build day.
    - All time starts on the first scanned day. If every scan comes after the build, it starts on the build day.
    - The days are null only in an index file without scans, which only `all` can be in an empty build. With no scans there's no office time zone to count days in.
  - **Check:**
    - `first_day` is no later than `last_day`.
    - Every period ends on the same day, within a day of the build's UTC date. That's as far as the check can go, since it doesn't know the office time zones.
    - All time starts on the first scanned day.
    - The days are only null without scans.
  - **Frontend:**
    - The chart's brush starts on the period's days and ends after the last day's bar, so the detail chart opens zoomed.
    - All time isn't zoomed and keeps the old hint, since nothing is zoomed. The other periods show the ticket's hint.
    - Choosing a different period re-zooms. Clicking the period that's already selected doesn't undo a hand-brushed zoom.
  - **Contract:** still version 3.
  - **Tests:**
    - Build: every period's days, a location with nothing scanned in a period, and a build without scans.
    - Check: five breakages.
  - **Checked:**
    - The real data builds and passes the check.
    - Compiling the spec headless with Vega gave detail domains of one day for Today, 8 days for Last 7 days, and the 1st onwards for This month. All time was the whole history.
    - Not checked in a browser.

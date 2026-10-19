# 09: Top scans

**What to build:** The front page opens with a **Top scans** panel: the codes scanned most often within a chosen period, within the selected location. Office management sees what to buy next. Unknown products are included but flagged, with a link to add them to OpenFoodFacts so they get a name. Terms (Top scans, Period, Unknown product, Office time zone) are as defined in GLOSSARY.md. Decided in a grilling session on 2026-10-19.

**Blocked by:** None (01–08 are done).

**Status:** resolved

### Periods

Every period ends at the build time.

| Period | `?period=` | Starts |
|---|---|---|
| Today | `today` | 00:00 today, office time |
| This work week | `this-work-week` | Monday 00:00 this week, office time; weekends included |
| Last 7 days | `last-7-days` | 7 × 24 h before the build |
| This month | `this-month` | 00:00 on the 1st, office time |
| Last 30 days | `last-30-days` | 30 × 24 h before the build |
| This year | `this-year` | 00:00 on 1 January, office time |
| Last 365 days | `last-365-days` | 365 × 24 h before the build |
| All time | `all-time` | (no start) |

- **Calendar periods:** these start in each scan's own office time zone, so `all` and parent locations spanning several zones stay correct.
- **Rolling periods:** these are exact durations back from the build; a scan exactly at the cutoff counts.
- **Later scans:** scans after the build time fall in no period.

### Acceptance criteria

- [x] The Scan summary module ranks top scans for every period, as of the build time. This is a separate `top_scans` function rather than part of `summarise`, because only index files show top scans and computing them for every code file tripled the build time. Each list has at most N codes (N = 10, in config), most scans first, ties ordered by the most recent scan.
- [x] Each top-scans row carries: code, name, brands, whether the product is known (OpenFoodFacts has it), the count, and its share of all scans in that period.
- [x] Each location's index file gains `top_scans`, an object keyed by period ID. Every period is always present; a period with no scans has an empty list.
- [x] The front page shows a "Top scans" panel at the top, above the scans-per-day chart, with a tab for each period. The chosen period is kept in `?period=`, defaulting to `last-30-days`; an unknown value falls back to the default. `?location=` still applies.
- [x] Each row shows rank, the product (name and brands, or "Unknown product"), the code, the count and the share. It links to its code page, keeping `?location`.
- [x] A known product without a name reads "Unnamed product". Unknown products read "Unknown product" and show a "Not in OpenFoodFacts" tag (icon and text, not colour alone). For numeric codes, it also links to `https://world.openfoodfacts.org/cgi/product.pl?type=search_or_add&action=process&code={code}`. Known products without a name aren't flagged.
- [x] An empty period says so ("No scans today", "No scans in the last 7 days", …), and its tab stays visible.
- [x] Scan summary tests cover:
  - period boundaries: today and this work week across office midnight; Monday in Bangkok vs UTC; the 1st of the month; 1 January; the rolling cutoffs,
  - mixed office time zones,
  - ties,
  - the size limit,
  - share,
  - unknown products.
- [x] Build tests cover the `top_scans` file contract.

## Comments

- 2026-10-19: Implemented.
  - **Backend:** `scan_summary.top_scans(scans, limit=, now=)` ranks codes per period. Calendar starts are worked out in each scan's office time zone from the build time (`CALENDAR_PERIODS`); rolling cutoffs are inclusive (`ROLLING_PERIODS`); scans after the build are excluded. `with_products` adds `product_known`. Index files gain `top_scans`, and `TOP_SCANS_LIMIT` = 10 is in config.
  - **Frontend:** a "Top scans" panel at the top of the index page, with 8 period tabs in `?period=` (default `last-30-days`, unknown values fall back). Rows show rank, the product ("Unnamed product" when known but unnamed, "Unknown product" plus a "? Not in OpenFoodFacts" tag and an "Add it" link for numeric unknown codes), code, count and share, and link to the code page.
  - **Tests:** 15 Scan summary tests for top scans:
    - each calendar boundary either side of Bangkok midnight,
    - Bangkok already on Monday while London is still on Sunday,
    - exact rolling cutoffs,
    - mixed zones, ties, the size limit, share, unknown products and later scans.
  - Plus a build test for the file contract.
  - **Real data:** All time is led by Soda water (446). Today and This work week are empty, as the latest live scan was on 16 Oct. Recent periods are dominated by unknown products.
  - **Checked:** rendered in happy-dom (the default, a bogus value, an empty period, and a tab click that keeps `?location=`). Not seen in a real browser.
- 2026-10-19: Moved below the scans-per-day chart, at the user's request. The page now reads chart, then top scans, then latest scans.
- 2026-10-19: At the user's request, the "? Not in OpenFoodFacts" tag was removed. An unknown product now shows "Unknown product" and, for barcodes, an "Add it to OpenFoodFacts" link.

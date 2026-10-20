# 24: One period selector for the index page

**What to build:** the index page has a single period selector, a bar of period tabs at the top above Scans per day, and every period-driven section follows it. Today the tabs sit inside Top scans, although the healthiest and least healthy products follow them too. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** resolved

Decisions from the design session:

- **Where:** the period tabs move out of Top scans into a bar at the top of the index page, above the chart.
  - The period is still kept in `?period=`, defaulting to the last 30 days, and an unknown value falls back to the default.
  - The header and the other pages don't change.
- **"Unknown only":** stays with Top scans, since it only affects that list. It's still kept in `?unknown=1`.
- **Headings:** the period-driven sections name the period, e.g. "Top scans · Last 30 days" and "Healthiest and least healthy products · Last 30 days". The healthiest and least healthy products' coverage line drops its period prefix ("Based on the … scans with a Nutri-Score.").
- **Latest scans:** stays independent of the period and stays last on the page.
- **Chart:** Scans per day is unchanged in this ticket. Zooming it to the period is ticket 25.
- **Vocabulary:** say "period", not "time-line" (GLOSSARY.md).

- [x] The period tabs sit at the top of the index page, and Top scans keeps only "Unknown only".
- [x] Top scans and the healthiest and least healthy products follow the selected period and name it in their headings.
- [x] The coverage line no longer starts with the period's name.
- [x] Changing the period, the location or "Unknown only" keeps the other URL parameters, as before.
- [x] The PRD (§6.2) describes the selector and the headings.

## Comments

- 2026-10-20: Implemented.
  - **Selector:** a new PeriodSelector sits at the top of the index page. Top scans keeps only "Unknown only".
  - **Accessibility:** one selector now drives several sections, so the tabs became a labelled button group with `aria-pressed` rather than an ARIA tablist with a single tabpanel.
  - **Headings:** the index page puts the period in the Top scans and healthiest and least healthy headings. The coverage line lost its period prefix.
  - **Tests:** no frontend tests (PRD §9).
  - **Checked:**
    - tsc, lint and the build pass.
    - A server-side render with `?location=thailand&period=last-30-days&unknown=1` showed Last 30 days pressed, "Unknown only" on, and both lists for the period.
    - Not checked in a browser.

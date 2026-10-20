# 24: One period selector for the index page

**What to build:** the index page has a single period selector, a bar of period tabs at the top above Scans per day, and every period-driven section follows it. Today the tabs sit inside Top scans, although the healthiest and least healthy products follow them too. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

Decisions from the design session:

- **Where:** the period tabs move out of Top scans into a bar at the top of the index page, above the chart.
  - The period is still kept in `?period=`, defaulting to the last 30 days, and an unknown value falls back to the default.
  - The header and the other pages don't change.
- **"Unknown only":** stays with Top scans, since it only affects that list. It's still kept in `?unknown=1`.
- **Headings:** the period-driven sections name the period, e.g. "Top scans · Last 30 days" and "Healthiest and least healthy products · Last 30 days". The healthiest and least healthy products' coverage line drops its period prefix ("Based on the … scans with a Nutri-Score.").
- **Latest scans:** stays independent of the period and stays last on the page.
- **Chart:** Scans per day is unchanged in this ticket. Zooming it to the period is ticket 25.
- **Vocabulary:** say "period", not "time-line" (GLOSSARY.md).

- [ ] The period tabs sit at the top of the index page, and Top scans keeps only "Unknown only".
- [ ] Top scans and the healthiest and least healthy products follow the selected period and name it in their headings.
- [ ] The coverage line no longer starts with the period's name.
- [ ] Changing the period, the location or "Unknown only" keeps the other URL parameters, as before.
- [ ] The PRD (§6.2) describes the selector and the headings.

## Comments

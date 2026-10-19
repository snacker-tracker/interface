# 11: Top scans of unknown products

**What to build:** In Top scans, an "Unknown only" toggle shows the most-scanned **unknown products** in the chosen period, so office management can see which missing products matter most and add them to OpenFoodFacts. Terms (Top scans, Period, Unknown product) are as defined in GLOSSARY.md. Requested 2026-10-19.

**Blocked by:** None (09 is done).

**Status:** resolved

- [x] For every period, the build also ranks unknown products only: up to N codes (the same N = 10), with the same ordering and ties as top scans. Each list ranks all unknown codes, not just those in the overall top N.
- [x] Share stays relative to **all** scans in the period, so it reads as the product's share of everything taken.
- [x] Unknown means OpenFoodFacts doesn't have the product (`known` false). Products it has without a name ("Unnamed product") aren't included.
- [x] Each location's index file gains `top_unknown_scans`, keyed by period ID like `top_scans`. Every period is always present.
- [x] The Top scans panel has an "Unknown only" toggle next to the period tabs, kept in the URL as `?unknown=1` (absent means off), alongside `?period=` and `?location=`.
- [x] With the toggle on, the list shows that period's top unknown products, with the same rows (including "Add it to OpenFoodFacts" for barcodes). An empty list says "No unknown products scanned today" (etc.).
- [x] Tests at the top-scans seam cover: unknown codes ranked beyond the overall top N, share relative to all scans, and unnamed known products being excluded. A build test covers the file contract.

## Comments

- 2026-10-19: Implemented.
  - **Backend:** `top_scans(..., unknown_only=True)` ranks unknown products, with shares of all scans in the period. Index files gain `top_unknown_scans`.
  - **Frontend:** an "Unknown only" toggle beside the period tabs, kept in `?unknown=1`. It sits outside the tablist for accessibility.
  - **Tests:** unknown codes ranked below the overall top N, share relative to all scans, unnamed products excluded, every period present, and the build file contract.
  - **Real data:** the top unknown products over all time are 8855366008458 (89 scans) and 8858702423304 (87).
  - **Checked:** rendered in happy-dom (toggle on and off updates the URL; empty message). The CSS selectors only gained new rules. Not seen in a real browser.

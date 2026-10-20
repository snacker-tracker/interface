# 23: Healthiest and least healthy products

**What to build:** a new index-page section, "Healthiest and least healthy products" (GLOSSARY.md), below Top scans. It has two lists side by side, which stack on phones: the healthiest products and the least healthy products scanned in the period. Office management can see which healthy products people actually take, and which unhealthy ones. Requested 2026-10-20.

**Blocked by:** 22 (Nutri-Score in the scan lists).

**Status:** resolved

Decisions from the design session:

- **Which period and location:** the section follows the selected location and Top scans' period, using the same `?period=`. It has no tabs of its own. The "Unknown only" toggle doesn't affect it, since unknown products have no Nutri-Score.
- **What counts:** products with a Nutri-Score that were scanned in the period. A product without one is left out.
- **Ranking:** Nutri-Score grade first, then the product's scans in the period. Ties go to the most recently scanned, as in Top scans.
  - **Healthiest** is A first, and the most scanned first within each grade.
  - **Least healthy** is E first, and the most scanned first within each grade.
- **No overlap:** the lists never share a product. The period's graded products are ranked best first and split in halves:
  - The better half, up to 10, is Healthiest.
  - The worse half, up to 10, is Least healthy, in its own worst-first order.
  - With an odd count, the extra product goes to Healthiest. For example, 7 products split into 4 healthiest and 3 least healthy, and 1 product goes to Healthiest only.
  - With 20 or more graded products, the lists are simply the 10 best and the 10 worst.
  - The 10 is the configured top-scans size.
- **Rows:** rank, the product as in the other scan lists with its compact Nutri-Score badge, and its scan count in the period. There's no share.
- **Coverage line:** the section says how many of the period's scans it covers, e.g. "Based on the 1,204 of 2,310 scans with a Nutri-Score."
- **Empty states:** the section always keeps its heading.
  - With no graded products in the period, it says e.g. "No products with a Nutri-Score scanned today."
  - With only one, Least healthy says "Nothing else to compare."
- **Naming:** the UI says "products", not "snacks", following the glossary.
- **On the real data, for all time:** Healthiest starts with the A products (20 products, 140 scans in all). Least healthy starts with Crispy Pork Rinds (E, 253 scans).
- **Contract:** the grades are version 3. This adds fields, so it's bumped to 4 if version 3 has been deployed when this lands; otherwise it stays at 3.

- [x] Index files carry, for every period, the healthiest and least healthy lists and the coverage counts, meaning the graded scans and all scans in the period. The schema, the generated frontend types and the check cover them.
- [x] The check enforces the rules:
  - The lists never share a product.
  - Each list holds at most 10 products.
  - Every product has a Nutri-Score.
  - Each list is in its own order.
  - The halves split is followed.
- [x] The index page shows the section below Top scans, following the selected location and period, with the rows, the coverage line and the empty states above.
- [x] Build tests cover:
  - ranking by grade then scans
  - the halves split with an odd count
  - a single graded product
  - a period with none
  - products without a Nutri-Score being left out
- [x] The real data builds and the check passes.
- [x] The PRD describes the section.

## Comments

- 2026-10-20: Implemented.
  - **Backend:**
    - Index files gain `healthiest_and_least_healthy`. Each period has `healthiest`, `least_healthy` (top-scan rows, whose share the UI doesn't show), `graded_scans` and `scans`.
    - The healthiest are the better half by grade then scans. The least healthy are the worst of the rest, so a big period lists the most-scanned worst products, not leftovers.
    - Top scans and these lists share the per-code counting.
  - **Check:** every rule above, plus listed counts not exceeding the graded scans.
  - **Frontend:**
    - A new panel below Top scans, which reads Top scans' period.
    - The period labels moved next to the period hook so both panels share them.
    - Top-scan rows can leave out the share.
    - The coverage line starts with the period's name, since the panel has no tabs of its own.
  - **Contract:** still version 3, since version 3 isn't deployed yet.
  - **Tests:**
    - Scan summary seam: grade before scans, the odd split, a single E product, the most-scanned worst products, products without a Nutri-Score left out but counted for coverage, and empty periods.
    - Build: every period, and per location.
    - Check: seven breakages.
  - **Real data:**
    - The build passes the check.
    - All time: 3,865 of 8,084 scans are graded. Healthiest starts with a pistachio drink (A, 29 scans), and Least healthy with Crispy Pork Rinds (E, 253).
    - Last 30 days: only 3 graded scans, so Healthiest has an A and a C, and Least healthy a C.
    - A server-side render showed the empty, single and normal states.
    - Not checked in a browser.

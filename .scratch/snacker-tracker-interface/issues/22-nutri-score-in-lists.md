# 22: Nutri-Score in the scan lists

**What to build:** Top scans, Latest scans and the scanners page's last scan show a product's Nutri-Score, so the most popular snacks show how healthy they are. Requested 2026-10-20.

**Blocked by:** 21 (Grades on the code page).

**Status:** resolved

Decisions from the design session:

- **Nutri-Score only:** rows show only the Nutri-Score. The NOVA group and Green-Score stay on the code page.
- **Looks:** the badge is a compact form of the card's badge, with the same tooltip, placed after the brands.
- **No name:** a product OpenFoodFacts has without a name still shows its badge, after its code and the "On OpenFoodFacts" link. The rule is that a row shows the Nutri-Score whenever there is one.
- **No Nutri-Score:** a product without one, including an unknown product, shows no badge.
- **Contract (still version 2).**

- [x] Top scans, scan rows and last scans carry the Nutri-Score, and the schema, the check and the generated frontend types cover it.
- [x] Top scans, Latest scans and the scanners page's last scan show the compact badge whenever the product has a Nutri-Score.
- [x] Build tests cover a top scan and a scan row with and without a Nutri-Score.
- [x] The real data builds and the check passes.
- [x] The PRD describes the badge in the lists.

## Comments

- 2026-10-20: Implemented.
  - **Backend:** scans get their product's Nutri-Score, which top scans, scan rows and last scans carry.
  - **Check:** a Nutri-Score on an unknown product's row is a violation.
  - **Frontend:**
    - The Grades module gains a compact `NutriScoreBadge`, which reuses the card badge's colours and tooltip.
    - The scan-list product cell shows it last, after the brands or after the code and its OpenFoodFacts link.
    - The scanners page's last scan shows it after the archive tag.
  - **Tests:**
    - A build test covers top scans, index and code-page scan rows, and last scans, both with and without a Nutri-Score.
    - A check breakage covers an unknown product with a Nutri-Score.
    - The exact-shape expectations gained the field.
  - **Real data:**
    - The build passes the check. The all-time top scans start Soda water (B) and Crispy Pork Rinds (E).
    - No product is both graded and nameless, so that case was only rendered from made-up props.
    - A server-side render of the list cell showed all four cases.
    - Not checked in a browser.

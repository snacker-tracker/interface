# 22: Nutri-Score in the scan lists

**What to build:** Top scans, Latest scans and the scanners page's last scan show a product's Nutri-Score, so the most popular snacks show how healthy they are. Requested 2026-10-20.

**Blocked by:** 21 (Grades on the code page).

**Status:** ready-for-agent

Decisions from the design session:

- **Nutri-Score only:** rows show only the Nutri-Score. The NOVA group and Green-Score stay on the code page.
- **Looks:** the badge is a compact form of the card's badge, with the same tooltip, placed after the brands.
- **No name:** a product OpenFoodFacts has without a name still shows its badge, after its code and the "On OpenFoodFacts" link. The rule is that a row shows the Nutri-Score whenever there is one.
- **No Nutri-Score:** a product without one, including an unknown product, shows no badge.
- **Contract (still version 2).**

- [ ] Top scans, scan rows and last scans carry the Nutri-Score, and the schema, the check and the generated frontend types cover it.
- [ ] Top scans, Latest scans and the scanners page's last scan show the compact badge whenever the product has a Nutri-Score.
- [ ] Build tests cover a top scan and a scan row with and without a Nutri-Score.
- [ ] The real data builds and the check passes.
- [ ] The PRD describes the badge in the lists.

## Comments

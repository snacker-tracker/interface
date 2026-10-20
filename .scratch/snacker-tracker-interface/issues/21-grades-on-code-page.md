# 21: Grades on the code page

**What to build:** a code page's product card shows the product's grades (GLOSSARY.md) from OpenFoodFacts: its Nutri-Score (A–E), NOVA group (1–4) and Green-Score (A–F). Office-goers can see at a glance how healthy, how processed and how green a snack is. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

Decisions from the design session:

- **Grades, not scores:** the card shows the grades, not the raw numeric scores. Use OpenFoodFacts's `nutriscore_grade`, `nova_group` and `environmental_score_grade`. The raw `nutriscore_score` and `environmental_score_score` aren't shown.
- **Missing grades:** a grade OpenFoodFacts doesn't have is left out, whether it's missing, "unknown" or "not-applicable". A product with no grades shows no grades. Only OpenFoodFacts grades products, so archive-only products and products no source has never show grades.
- **Looks:** each grade is our own small text badge, e.g. "Nutri-Score B", "NOVA 4" or "Green-Score D", on the grade's colour. The text is always readable on its own, so colour isn't the only signal. Badges aren't hotlinked from OpenFoodFacts.
- **Tooltips:** each badge's tooltip is one fixed sentence saying what that grade means, e.g. NOVA 4 → "Ultra-processed food".
- **Name:** use "Green-Score", OpenFoodFacts's current name, not "Eco-Score".
- **Expected coverage on the real data, out of 508 products OpenFoodFacts has:** about 288 Nutri-Scores, 203 NOVA groups and 181 Green-Scores.
- **Contract (still version 2):** version 2 isn't deployed yet, so these fields ship in the same deploy.

- [ ] The products table carries the three grades, with "unknown", "not-applicable" and blank values stored as no grade. This is a column change, so the existing table is re-extracted once without `--force`.
- [ ] Product files carry the three grades, and the schema, the check and the generated frontend types cover them.
- [ ] The product card shows a badge with a meaning tooltip for each grade the product has, and nothing for the grades it lacks.
- [ ] Tests cover extracting a product with grades, one whose grades are "unknown" or "not-applicable", and a product file carrying the grades.
- [ ] The real data builds and the check passes.
- [ ] The PRD describes the grades on the card, and its out-of-scope line no longer excludes Nutri-Score and NOVA, only nutrients and other nutrition data.

## Comments

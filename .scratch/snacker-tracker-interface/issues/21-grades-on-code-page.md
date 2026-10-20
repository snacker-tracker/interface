# 21: Grades on the code page

**What to build:** a code page's product card shows the product's grades (GLOSSARY.md) from OpenFoodFacts: its Nutri-Score (A–E), NOVA group (1–4) and Green-Score (A+–F). Office-goers can see at a glance how healthy, how processed and how green a snack is. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** resolved

Decisions from the design session:

- **Grades, not scores:** the card shows the grades, not the raw numeric scores. Use OpenFoodFacts's `nutriscore_grade`, `nova_group` and `environmental_score_grade`. The raw `nutriscore_score` and `environmental_score_score` aren't shown.
- **Missing grades:** a grade OpenFoodFacts doesn't have is left out, whether it's missing, "unknown" or "not-applicable". A product with no grades shows no grades. Only OpenFoodFacts grades products, so archive-only products and products no source has never show grades.
- **Looks:** each grade is our own small text badge, e.g. "Nutri-Score B", "NOVA 4" or "Green-Score D", on the grade's colour. The text is always readable on its own, so colour isn't the only signal. Badges aren't hotlinked from OpenFoodFacts.
- **Tooltips:** each badge's tooltip is one fixed sentence saying what that grade means, e.g. NOVA 4 → "Ultra-processed food".
- **Name:** use "Green-Score", OpenFoodFacts's current name, not "Eco-Score".
- **Expected coverage on the real data, out of 508 products OpenFoodFacts has:** about 288 Nutri-Scores, 203 NOVA groups and 181 Green-Scores.
- **Contract (still version 2):** version 2 isn't deployed yet, so these fields ship in the same deploy.

- [x] The products table carries the three grades, with "unknown", "not-applicable" and blank values stored as no grade. This is a column change, so the existing table is re-extracted once without `--force`.
- [x] Product files carry the three grades, and the schema, the check and the generated frontend types cover them.
- [x] The product card shows a badge with a meaning tooltip for each grade the product has, and nothing for the grades it lacks.
- [x] Tests cover extracting a product with grades, one whose grades are "unknown" or "not-applicable", and a product file carrying the grades.
- [x] The real data builds and the check passes.
- [x] The PRD describes the grades on the card, and its out-of-scope line no longer excludes Nutri-Score and NOVA, only nutrients and other nutrition data.

## Comments

- 2026-10-20: Implemented.
  - **Backend:**
    - The products table gains `nutri_score`, `nova_group` and `green_score`. Off-scale values ("unknown", "not-applicable", blank) are stored as no grade.
    - Product files carry the grades.
  - **Check:** grades on the product file of a product OpenFoodFacts doesn't have are a violation. The PRD's §7.4 Names rule now covers product files too, which closes a review finding from 18–20.
  - **Frontend:** a new Grades component shows text badges in OpenFoodFacts's colours, the same in both themes, each with a meaning tooltip.
  - **Real data:**
    - Re-extraction ran once, because of the new columns.
    - 288 Nutri-Scores, 203 NOVA groups and 181 Green-Scores, none of them on unknown products.
    - The build passes the check.
    - A server-side render showed all three grades on 3046920028004, none on a known product without grades, and none on the archive-only 220000.
    - Not checked in a browser.
  - **Contract:** still version 2. Deploy it with the frontend, as for 18–20.
- 2026-10-20: Follow-ups from the review.
  - The Green-Score scale gains A+ (OpenFoodFacts's `a-plus`), above A.
  - The NOVA group and Green-Score fields have their own descriptions.
  - The contract is bumped to version 3 for the grades (tickets 21–22), rather than staying at 2.

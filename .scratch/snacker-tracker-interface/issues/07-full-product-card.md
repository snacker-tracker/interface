# 07: Full product card

**What to build:** On a code page, office management sees enough to buy the right item again: quantity, a product image, category tags, and a link to the product on OpenFoodFacts, alongside the name and brands. See PRD R5.

**Blocked by:** 06 (Code page).

**Status:** ready-for-agent

- [ ] Decide how to build the product image URL from the OpenFoodFacts `images` column and code, and record the decision (an ADR if it isn't obvious).
- [ ] Product extraction carries quantity, categories, the image URL and the OpenFoodFacts product URL. Products already extracted are refreshed, or extraction is forced, so the new columns are present.
- [ ] The product file includes these fields, and categories are a list.
- [ ] The code page shows quantity, the image (degrading gracefully when missing or failing to load), category tags and the OpenFoodFacts link.
- [ ] Product extraction tests cover the new fields, including products that have no image or categories.

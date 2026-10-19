# 07: Full product card

**What to build:** On a code page, office management sees enough to buy the right item again: quantity, a product image, category tags, and a link to the product on OpenFoodFacts, alongside the name and brands. See PRD R5.

**Blocked by:** 06 (Code page).

**Status:** resolved

- [x] Decide how to build the product image URL from the OpenFoodFacts `images` column and code, and record the decision (an ADR if it isn't obvious).
- [x] Product extraction carries quantity, categories, the image URL and the OpenFoodFacts product URL. Products already extracted are refreshed, or extraction is forced, so the new columns are present.
- [x] The product file includes these fields, and categories are a list.
- [x] The code page shows quantity, the image (degrading gracefully when missing or failing to load), category tags and the OpenFoodFacts link.
- [x] Product extraction tests cover the new fields, including products that have no image or categories.

## Comments

- 2026-10-19: Implemented.
  - **Images:** the image URL decision is recorded in docs/adr/0001. The selected front image is hotlinked in the product's language, then English, then any; 400px; the code is padded to 13 digits and split 3/3/3/rest. Checked against the live image server: 11 of 12 sampled URLs loaded (the server was slow, about 16s per image).
  - **Products table:** gains `known`, `quantity`, `categories` (a list, language prefixes stripped, without repeats), `image_url` and `off_url`. A table in the old schema is re-extracted automatically.
  - **Known vs unknown:** a known product is one OpenFoodFacts has, even without a name. This was decided during review and matches GLOSSARY "Unknown product".
  - **product.json:** carries the full card, or null for an unknown product.
  - **Code page:** shows a lazy-loaded image in a fixed frame, falling back to "No image" when it's missing or fails to load, plus name, brands, quantity, category tags, the code and a "View on OpenFoodFacts" link.
  - **Real data:** 508 known products, 479 with an image, 258 with categories.
  - **Not verified:** the onError fallback hasn't been tried in a browser.

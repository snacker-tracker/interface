# 20: The code page shows Snacker archive names

**What to build:** a code page's product card uses the Snacker archive too.
- **Archive-only code:** the card's heading is the archive name with the "Snacker archive" tag. Below it, the card says "Not on OpenFoodFacts" and links to "Add it to OpenFoodFacts" when the code is a barcode. It has no image, brands, quantity or categories.
- **Known product without an OpenFoodFacts name:** the card shows the archive name, tagged, with its OpenFoodFacts details and link as before.
- **Neither source:** the card still reads "Unknown product" with the raw code.

Requested 2026-10-20.

**Blocked by:** 19 (The Snacker archive names products in the lists).

**Status:** resolved

Contract (still version 2; the shape was agreed in the design session):

```
ProductFile  + known: bool
               product: Product | null   # null only when no source has the code
Product      + name_source: "openfoodfacts" | "snacker-archive" | null
               off_url: str | null       # null when OpenFoodFacts doesn't have it
```

- [x] Product files carry `known`. `product` is non-null for an archive-only code (name only, `off_url` null) and null only when neither source has the code.
- [x] The product carries `name_source`, null exactly when the name is null, and the check enforces it.
- [x] The schema and the generated frontend types are regenerated.
- [x] The product card renders the three cases above, with "Snacker archive" tagging only names from the archive.
- [x] Build tests cover a product file for an archive-only code, for a known product named by the archive, and for a code no source has.
- [x] The real data builds and the check passes. Version 2 is then ready to deploy, with the backend data and the frontend together.
- [x] PRD R5 and C1 describe the card.

## Comments

- 2026-10-20: Implemented.
  - **Backend:** `product_files` replaces `known_products`, and every looked-up code gets its file with `known`. The product is null only when no source has the code. Codes scanned since the last extraction get `known: false` and no product.
  - **Check:** the product-file name source follows the same rule as the lists.
  - **Frontend:** the card takes the whole product file. It tags archive names, shows "View on OpenFoodFacts" only when `off_url` is set, and adds "Not on OpenFoodFacts" with the add link for an archive-only product.
  - **Tests:**
    - A build test covers the three product-file cases.
    - A check breakage covers a product name without a source.
    - The existing product-file test gained the new fields.
  - **Checked:**
    - The real data builds and passes the check. `220000` is now an archive-only product.
    - A server-side render of the card showed all three cases.
    - Not checked in a browser.
  - **Next:** version 2 is ready to deploy. Rebuild `public-data`, which is already done locally, and deploy it with the frontend.

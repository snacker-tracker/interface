# 05: Product names in scan lists

**What to build:** An office-goer sees the product name and brand in the recent-scans list instead of a bare barcode. Codes with no product information show as "Unknown product" plus the raw code, and still count everywhere. Product data comes from a separate extraction step that pulls a small products table out of the 8 GB OpenFoodFacts file, so routine builds don't read the big file. See PRD R3, R5 and §8.1.

**Blocked by:** 02 (Index page).

**Status:** ready-for-agent

- [ ] A product extraction CLI step reads the OpenFoodFacts food parquet and writes a small products table holding only scanned codes and the needed columns (at least code, name and brands; it is extended in tickets 06 and 07).
- [ ] The name is the `main` entry of the multilingual `product_name`, falling back to the first entry. Brands come from `brands`, since there is no `brand` column.
- [ ] Extraction reruns only when scanned codes are missing from the existing products table, or when forced.
- [ ] The build reads the products table, never the OpenFoodFacts file.
- [ ] Scan rows carry the product name and brands, or null when there's no match.
- [ ] The UI shows the name and brands, or "Unknown product" plus the raw code.
- [ ] Product extraction tests (seam 2) use a tiny fixture parquet with the real column types and cover keeping only requested codes, leaving out unmatched codes, and choosing the name with fallback.
- [ ] End-to-end build tests cover rows with and without product matches.

# 05: Product names in scan lists

**What to build:** An office-goer sees the product name and brand in the recent-scans list instead of a bare barcode. Codes with no product information show as "Unknown product" plus the raw code, and still count everywhere. Product data comes from a separate extraction step that pulls a small products table out of the 8 GB OpenFoodFacts file, so routine builds don't read the big file. See PRD R3, R5 and §8.1.

**Blocked by:** 02 (Index page), 02a (Prefactor: Scan summary and Locations).

**Status:** resolved

- [x] A product extraction CLI step reads the OpenFoodFacts food parquet and writes a small products table holding only scanned codes and the needed columns (at least code, name and brands; it is extended in tickets 06 and 07).
- [x] The name is the `main` entry of the multilingual `product_name`, falling back to the first entry. Brands come from `brands`, since there is no `brand` column.
- [x] Extraction reruns only when scanned codes are missing from the existing products table, or when forced.
- [x] The build reads the products table, never the OpenFoodFacts file.
- [x] Scan summary (02a) owns the scan row's shape, so adding name and brands happens there.
- [x] Scan rows carry the product name and brands, or null when there's no match.
- [x] The UI shows the name and brands, or "Unknown product" plus the raw code.
- [x] Product extraction tests (seam 2) use a tiny fixture parquet with the real column types and cover keeping only requested codes, leaving out unmatched codes, and choosing the name with fallback.
- [x] End-to-end build tests cover rows with and without product matches.

## Comments

- 2026-10-19: Implemented.
  - **Extraction:** `snacker extract-products --raw … --food … --products …` writes one row per scanned code (code, name, brands). The name is the `main` entry, then the first entry; blank or missing names and brands become null.
  - **Decision (user):** unknown codes are kept as rows with null name and brands instead of being left out, so "already looked up" means "in the table". This replaces the test line "leaving out unmatched codes".
  - **Reruns:** extraction reruns, for every code, only when a scanned code is missing from the table or `--force` is given.
  - **Build:** `snacker build` gains `--products`; it joins the table onto the scans and never reads the food parquet. Codes scanned since the last extraction count as unknown products.
  - **Rows and UI:** scan rows gain `name` and `brands`. The UI shows the name with brands underneath, or an italic "Unknown product", with the code in its own column.
  - **Real data:** extraction takes about 0.5s on the 8 GB file. 854 codes, 493 named; a rerun with nothing new is a no-op. 11 of the latest 25 scans are named; many recent Thai products aren't in OpenFoodFacts.

# 03: Extract products from Hugging Face into S3, from a laptop

**What to build:** `extract-products` reads the OpenFoodFacts file straight from Hugging Face, and reads the Snacker archive and writes the products table in S3. Local paths keep working.

**Blocked by:** 01 (the spike decides whether the `hf://` scan fits a Lambda run). Resolved: a plain `hf://` scan is rate-limited (HTTP 429) before it finishes. Instead, **resolve the URL once to its signed CDN URL and scan that**: about 2 minutes, 1.4 GB peak. See 01's comments.

**Status:** ready-for-agent

Decisions from the design session:

- **The OpenFoodFacts file:** `hf://datasets/openfoodfacts/product-database/food.parquet`, scanned lazily, so it's always the latest OpenFoodFacts data with no copy to keep in sync.
- **Locations:** the Snacker archive and the products table can each be a local path or an `s3://` URI.
- **Unchanged rules:**
  - A products table that already covers every scanned code isn't extracted again unless forced.
  - The archive's duplicated codes are still reported.

- [ ] Extraction runs with `hf://` and S3 locations as well as local ones.
- [ ] A run where every code is already covered reads nothing from Hugging Face.
- [ ] Existing extraction tests still pass, and the new location handling is tested at the extraction seam (to be agreed).
- [ ] A real run against a scratch location, with its timing recorded in the comments.

## Comments

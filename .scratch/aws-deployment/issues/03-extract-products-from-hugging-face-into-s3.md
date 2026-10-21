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

### 2026-10-21: implemented, S3 real run pending

`snacker extract-products --raw <dir | s3://…> --food <food.parquet | hf://…> --products <path | s3://…> [--archive <path | s3://…>]`, in `backend/src/snacker/extraction.py` (`update_products_at`).

**What it does:**
- **hf:// reads:** an `hf://` location is resolved to its signed CDN URL with one HEAD request (`signed_hf_url`, which sends `HF_TOKEN` if set), and Polars scans that URL.
- **Covered runs:** if the table already covers every scanned code, Hugging Face isn't contacted at all.
- **S3 table:** an S3 products table is copied down, updated, and put back as `application/vnd.apache.parquet`. A table not in S3 yet counts as absent and gets written.
- **Archive duplicates** are reported on every run, as before.
- **`--raw` also accepts `s3://`.** The ticket names only the archive and the table, but the Lambda will need it, and it reuses ticket 02's `fetch`.

**Tests**, at the agreed seam, through `FakeBucket` and a recording resolver (`tests/test_extraction_locations.py`):
- a covered S3 table means no resolver calls and no writes;
- a new code means one resolve and the table written back;
- a table not yet in S3 gets written;
- an `s3://` archive gives its names and reports its duplicates;
- a covered run still reports the duplicates.

The existing extraction tests pass unchanged.

**Real run, hf:// to a local table:**

The run was from a laptop in Thailand, using `--force` with the local archive. It took **128 s** for 854 codes: 493 named by OpenFoodFacts and 107 by the Snacker archive. Those counts match a run against the local copy of `food.parquet` (1 s). A covered run with `--food hf://…` returned at once, without contacting Hugging Face.

**Pending:** the real run against S3 (`s3://snacker-tracker-dev-working/…`). The AWS session expired, and the working bucket comes with ticket 06's main configuration. A scratch bucket would do until then.

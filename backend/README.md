# snacker (backend)

Build step that turns raw scanner events into the static JSON read by the frontend.
See `PRD.md` at the repo root for the data contract. Its shapes are defined in
`src/snacker/contract.py`; after changing them, rerun `snacker schema` to update the
committed JSON Schema (a test fails until you do).

```sh
uv run snacker extract-products --raw ../data/raw/data/scanner \
  --food ../data/openfoodfacts__product-database/food.parquet --products ../data/products.parquet \
  --archive ../data/codes.csv
uv run snacker build --raw ../data/raw/data/scanner --products ../data/products.parquet --out ../public-data
uv run snacker check --out ../public-data     # build already does this
uv run snacker schema --out ../contract/static-json.schema.json
uv run pytest
uv run mypy
```

`--archive` is the Snacker archive, the previous Snacker Tracker's product names. It is
merged only when the products table is written, so an extraction run without it leaves
archive names out until the next one (`--force` redoes it).

Office time zones live in `src/snacker/config.py`: a map from location prefix to IANA
time zone, where the longest prefix wins. A scanned location with no match stops the
build, so add a line there when a scanner goes into a new office.

`build` checks what it wrote against the whole output contract (PRD.md §7) before
publishing it: if any file breaks it, the build lists each violation, exits non-zero and
leaves the previous `data/` in place. The rejected build stays in `<out>/.data-building/`
for inspection. A build that passes replaces `data/` entirely, so files a build no longer
writes disappear.

## Extracting from Hugging Face and S3

`--food` can be `hf://datasets/openfoodfacts/product-database/food.parquet`, so each extraction
reads the latest OpenFoodFacts data without a local copy. `--raw`, `--archive` and `--products`
can each be an `s3://` URI.

```sh
uv run snacker extract-products --raw s3://snacker-tracker-dev/raw/data/scanner \
  --food hf://datasets/openfoodfacts/product-database/food.parquet \
  --products s3://snacker-tracker-dev-working/products.parquet \
  --archive s3://snacker-tracker-dev-working/snacker-archive.csv
```

- **The hf:// location is resolved once to its signed CDN URL, and Polars scans that.** Polars'
  own `hf://` reads send every range request through Hugging Face's resolver, and one scan
  exceeds its anonymous quota of 3,000 requests per 5 minutes (aws-deployment ticket 01).
  `HF_TOKEN` is sent if it's set. A run takes about 2 minutes and 1.4 GB.
- **A table that already covers every scanned code reads nothing from Hugging Face.**
- **A products table not in S3 yet** is written there, as a first local extraction would be.

## Building from and to S3

`--raw` and `--products` can each be an `s3://` URI, and `--out` can be `s3://<site bucket>`.
Credentials come from the standard AWS environment or profile.

```sh
uv run snacker build --raw s3://snacker-tracker-dev/raw/data/scanner \
  --products s3://snacker-tracker-dev-working/products.parquet --out s3://snacker-tracker-dev-site
```

- **Inputs are copied to a temporary directory first,** 64 objects at a time. That's 5× faster
  than globbing over S3 (aws-deployment ticket 01).
- **The build is checked before anything is published,** as with a local build. A rejected
  build is staged in a temporary directory, so it's listed but not kept for inspection.
- **An `s3://` input with nothing under it stops the build.** Building from it would
  publish an empty site over the real one.
- **Publishing touches only `data/` in the site bucket** (ADR 0004):
  - It uploads the files whose MD5 differs from the object's ETag, with
    `Content-Type: application/json` and `Cache-Control: max-age=60`.
  - It deletes the `data/` keys the build no longer writes.
  - It writes `meta.json` last.
  - It prints every key it uploaded or deleted.
- **The site bucket must use default S3 encryption (SSE-S3), not KMS.** With SSE-KMS an ETag
  isn't the file's MD5, so every file would look changed and be uploaded on every run.

## The Lambda image

One image runs both functions (`Dockerfile`, Python 3.13 on the AWS Lambda base image). The
function's handler picks the job:

- `snacker.handlers.build_handler` (the default command) builds and publishes `data/` to the site
  bucket. If any scanned code isn't in the products table, it then starts the extraction
  function asynchronously. Those codes are unknown products until a later build reads the new
  table. With no products table yet, every code is unknown.
- `snacker.handlers.extract_handler` looks up the scanned codes in OpenFoodFacts and writes the
  products table, as `extract-products` does.

Settings come from environment variables:

| Variable | Example |
| --- | --- |
| `SNACKER_RAW` | `s3://snacker-tracker-dev/raw/data/scanner` |
| `SNACKER_PRODUCTS` | `s3://snacker-tracker-dev-working/products.parquet` |
| `SNACKER_ARCHIVE` | `s3://snacker-tracker-dev-working/snacker-archive.csv` |
| `SNACKER_SITE` | `s3://snacker-tracker-dev-site` |
| `SNACKER_EXTRACT_FUNCTION` | `snacker-tracker-dev-extract` |
| `SNACKER_FOOD` (optional) | `hf://datasets/openfoodfacts/product-database/food.parquet`, the default |

`scripts/run-image-locally.sh` builds the image and runs both handlers in the Lambda runtime
emulator against real S3 (it needs Docker). Give the extraction function about 3 GB of memory:
its peak is 1.4 GB, and Lambda's CPU grows with memory.

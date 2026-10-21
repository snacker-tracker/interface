# 04: One container image with the build and extraction handlers

**What to build:** one Lambda container image runs either the build or the extraction, chosen by the handler. The build starts an extraction itself whenever scanned codes are missing from the products table, so new products get names without anyone stepping in.

**Blocked by:** 02 (Build from S3 and publish to S3), 03 (Extract products from Hugging Face into S3).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0003, 0006):

- **The image:** Python 3.13, with the backend installed by uv. A container image is needed because the Polars runtime alone is 179 MB unpacked, which leaves too little room in a .zip.
- **Configuration:** through environment variables: the raw, products, archive and site locations, and the name of the extraction function.
- **The build handler:** builds and publishes as in 02. If any scanned code isn't in the products table, it invokes the extraction function asynchronously. Those codes count as unknown until a later build reads the new table, as today.
- **The extraction handler:** extracts as in 03.
- **Dependencies:** marimo moves to a dev-only dependency.
- **Tags:** the image is tagged with the commit SHA. Where it's pushed is the shared ECR repository (ADR 0006), but pushing belongs to 06–07.

- [ ] The image builds locally and holds both handlers.
- [ ] Run with the Lambda runtime emulator against real S3, the build handler publishes and the extraction handler writes the products table.
- [ ] The build handler invokes extraction only when codes are missing. A test covers the decision, at a seam to be agreed.
- [ ] marimo is no longer a runtime dependency.

## Comments

### 2026-10-21: implemented, image build and emulator run pending (no Docker here)

**What it does:**
- **Handlers**, in `backend/src/snacker/handlers.py`:
  - `build_handler` (the image's default `CMD`) runs `handle_build`: fetch, build, check, publish. If the products table lacks any scanned code, it then calls `lambda:Invoke` with `InvocationType=Event` on `SNACKER_EXTRACT_FUNCTION`. With no table yet, it builds with an empty table, so every code is unknown, and starts the first extraction.
  - `extract_handler` reuses ticket 03's `update_products_at`.
- **Settings** come from `SNACKER_RAW`, `SNACKER_PRODUCTS`, `SNACKER_ARCHIVE`, `SNACKER_SITE` and `SNACKER_EXTRACT_FUNCTION`, plus an optional `SNACKER_FOOD`, which defaults to the Hugging Face file.
- **Image:** `backend/Dockerfile` uses `public.ecr.aws/lambda/python:3.13`, `uv export --no-dev` and `uv pip install --target $LAMBDA_TASK_ROOT`. The extraction function overrides the command with `snacker.handlers.extract_handler`.
  - The same install into a plain directory gives 226 MB of packages, without marimo, and both handlers import from there alone.
- **marimo** is now a dev dependency.

**Tests:** `tests/test_build_handler.py`, at the agreed seam `handle_build(settings, *, open_bucket, start_extraction, now)`:
- a covered table publishes and starts nothing;
- a missing code starts one extraction and still publishes;
- with no table yet, the build publishes every code as unknown and starts an extraction.

**IAM gap found:** `fetch` lists a key to tell an object from a prefix, but the build and extraction roles had no `ListBucket` on the working bucket. Both handlers would have failed in Lambda, and a missing table would have read as 403 rather than not found. `infra/admin/workload_roles.tf` now grants `ListBucket` limited to the `products.parquet*` and `snacker-archive.csv*` prefixes. Planned in dev (2 policies changed in place, Access Analyzer clean). **Admin apply pending.**

**Pending:** run `backend/scripts/run-image-locally.sh` on a machine with Docker. It builds the image tagged with the commit SHA, then runs the extraction handler and the build handler in the Lambda runtime emulator. They read prod raw, write to a scratch bucket, and publish to the dev site. The real asynchronous invoke under the build role is first exercised in 06.

# 02: Build from S3 and publish to S3, from a laptop

**What to build:** `snacker build` can read its inputs from S3 and publish to a site bucket, so the build that will run in Lambda can be run and checked from a laptop first. Local paths keep working exactly as today.

**Blocked by:** 01 (the spike decides whether raw events are read directly or copied first). Resolved: **copy first**, with a parallel download into a local directory (21 s against 110 s for a direct glob, and the direct read grows by about a minute a month). See 01's comments.

**Status:** resolved

Decisions from the design session (ADRs 0003, 0004):

- **Inputs:** the raw events location (scans and heartbeats) and the products table can each be a local path or an `s3://` URI.
- **Checked first:** the build writes to a local staging directory and runs the contract check as today. Nothing is published if the check fails.
- **Publishing to S3** (ADR 0004):
  - List `data/` in the site bucket.
  - Compare each built file's MD5 with the object's ETag.
  - Upload new or changed files with `Cache-Control: max-age=60` and the JSON content type.
  - Delete `data/` keys the build no longer writes.
  - Write `meta.json` last.
  - Touch nothing outside `data/`.
- **Publishing locally:** the swap of `data/` in one rename stays.
- **Credentials:** from the standard AWS environment or profile. Nothing is hard-coded.

- [x] The build runs with S3 inputs and an S3 output, as well as with local ones.
- [x] A second build with no new scans uploads only `meta.json` and deletes nothing.
- [x] Keys under `data/` that the build stopped writing are deleted, and keys outside `data/` are never touched.
- [x] Tests at the publish step's seam cover: uploading new and changed files only, deleting stale keys, `meta.json` last, and the cache and content-type headers. The seams are to be agreed before the tests are written.
- [x] A real run against a scratch bucket, with the uploads it made recorded in the comments.
- [x] The backend README documents the S3 usage and the default-encryption requirement (SSE-S3, not KMS).

## Comments

### 2026-10-21: implemented, real run pending

`snacker build --raw/--products <path | s3://…> --out <dir | s3://site-bucket>`, in `backend/src/snacker/storage.py`.

**What it does:**
- **Inputs:** `s3://` inputs are copied first, 64 objects at a time (ticket 01). A prefix keeps its layout, and an object becomes a file. An `s3://` input with nothing under it stops the build, so a mistyped prefix can't publish an empty site.
- **Publishing:** to the site bucket, as ADR 0004 describes. Local `--out` still swaps `data/` in one rename.

**Tests**, at the two agreed seams, both through an in-memory `FakeBucket`:
- `tests/test_publish_to_bucket.py` covers:
  - new and changed files only;
  - stale `data/` keys deleted, and nothing outside `data/` touched;
  - `meta.json` last;
  - the `application/json` and `max-age=60` headers.
- `tests/test_fetch.py` covers:
  - a local path passed through;
  - a prefix copied with its layout kept, respecting prefix boundaries;
  - a single object copied to a file;
  - an empty location stopping the build.

The boto3 adapter (`S3Bucket`) is left to the real run.

**Pending:**
- **The real run against a scratch bucket.** The AWS session expired. The CLI prints every key it uploads or deletes, for recording here.
- **"A second build uploads only `meta.json`".** This depends on what changes between the two builds. Top scans, healthiest/least healthy and `period_days` depend on the build time, so a second build that crosses a period boundary can change more files even with no new scans. Run the two builds back to back to check the acceptance line.

### 2026-10-21: real runs

These runs were from a laptop: raw events from `s3://snacker-tracker-prod/raw/data/scanner` (read-only, 11.8k objects), with the local `products.parquet`, published to the empty `s3://snacker-tracker-dev-site`. Prod raw was used because dev raw holds only 2 objects.

| Run | Took | Uploaded | Deleted |
| --- | --- | --- | --- |
| 1. Empty bucket | 35 s, including about 21 s for the copy | 3,466 files, `data/meta.json` last | 0 |
| 2. Straight after | 28 s | `data/meta.json` only | 0 |
| 3. After adding a stale `data/codes/stale-test/product.json` and a key outside `data/` | — | `data/meta.json` | `data/codes/stale-test/product.json`. The key outside `data/` was untouched, and removed by hand afterwards |
| 4. `--raw …/scannerX` (a mistyped prefix) | — | nothing | nothing. It exits 1 with `FileNotFoundError: nothing in s3://…/scannerX` |

- **Uploaded objects:** `Content-Type: application/json`, `Cache-Control: max-age=60`, `ServerSideEncryption: AES256`, and the ETag equals the MD5.
- **Error output:** the mistyped-prefix run exits with a traceback, not a one-line message. That could be tidied in 04.

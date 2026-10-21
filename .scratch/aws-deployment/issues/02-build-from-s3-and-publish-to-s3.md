# 02: Build from S3 and publish to S3, from a laptop

**What to build:** `snacker build` can read its inputs from S3 and publish to a site bucket, so the build that will run in Lambda can be run and checked from a laptop first. Local paths keep working exactly as today.

**Blocked by:** 01 (the spike decides whether raw events are read directly or copied first). Resolved: **copy first**, with a parallel download into a local directory (21 s against 110 s for a direct glob, and the direct read grows by about a minute a month). See 01's comments.

**Status:** ready-for-agent

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

- [ ] The build runs with S3 inputs and an S3 output, as well as with local ones.
- [ ] A second build with no new scans uploads only `meta.json` and deletes nothing.
- [ ] Keys under `data/` that the build stopped writing are deleted, and keys outside `data/` are never touched.
- [ ] Tests at the publish step's seam cover: uploading new and changed files only, deleting stale keys, `meta.json` last, and the cache and content-type headers. The seams are to be agreed before the tests are written.
- [ ] A real run against a scratch bucket, with the uploads it made recorded in the comments.
- [ ] The backend README documents the S3 usage and the default-encryption requirement (SSE-S3, not KMS).

## Comments

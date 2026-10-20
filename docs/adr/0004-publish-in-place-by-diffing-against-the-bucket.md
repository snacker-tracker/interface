# A build publishes in place, uploading only what differs from the bucket's listing

Locally, a build swaps `data/` in one rename. S3 has no atomic rename, so the build Lambda publishes in place instead:
1. It lists `data/` in the site bucket.
2. It compares each built file's MD5 with the object's ETag.
3. It uploads only new or changed files and deletes keys the build no longer writes.

This works because builds are deterministic: the same input produces byte-identical files.

We accepted that for a few seconds a page could read files from two builds. That's preferable to the alternative, which needs a contract change: upload each build to its own prefix and switch a pointer file. Comparing against the live listing rather than a stored manifest makes publishing self-correcting. A half-finished run, or a file changed by hand, is fixed on the next run, for 4 LIST requests per run.

## Consequences

- **Encryption:** the site bucket must use the default S3 encryption (SSE-S3). With SSE-KMS, or multipart uploads, an ETag is not the file's MD5, and every file would look changed.
- **Ownership of `data/`:** the build Lambda's role is the only writer of `data/`. CI deploys the frontend's files and is denied `data/*`, so a frontend sync can't wipe the data (ADR 0005).

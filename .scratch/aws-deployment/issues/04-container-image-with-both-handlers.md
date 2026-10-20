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

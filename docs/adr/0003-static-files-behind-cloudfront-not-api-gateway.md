# The data is served as static files behind CloudFront, not by Lambdas behind API Gateway

A scheduled build Lambda writes the static JSON to the site bucket, and CloudFront serves it with the frontend. Serving each request from Lambdas behind API Gateway was considered, to save on S3 PUT requests. It was rejected because the PUT cost turned out to be negligible.

We measured two builds 15 minutes apart on the real data:
- With no new scans, 1 of 3,466 files changed (`meta.json`).
- Across Bangkok midnight, 6 changed.
- A build after new scans changes about 15.

Uploading only changed files (ADR 0004) therefore means at most about 60k PUTs a month, about $0.30. Re-uploading every file every run would be about 10M PUTs a month, about $50.

Serving through API Gateway would not have cut any of that cost:
- **Reads cost more.** A request through API Gateway and Lambda is billed for both (about $1 + $0.20 per million, plus compute). A static file costs one S3 GET at about $0.40 per million, or less when CloudFront answers from cache.
- **The data still has to be precomputed and stored.** Building per request is not viable: a build takes 7 s and 700 MB.
- **A Polars image starts slowly,** which long cache times would hide only by serving staler data than the 15-minute build.

## Consequences

- The frontend stays a static app that reads files (PRD §7); there is no runtime code to operate.
- If read traffic grows, CloudFront's cache absorbs it; data files carry a short `Cache-Control` (60 s), hashed assets a long one.

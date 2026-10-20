# 06: Staging runs on Lambda behind CloudFront

**What to build:** a working staging environment. Every 15 minutes a Lambda builds the data from production's raw events, and the staging site serves it with the frontend through CloudFront on `staging.<domain>`.

**Blocked by:** 04 (One container image), 05 (Admin Terraform).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0003–0006):

- **The main configuration, applied by CI:** one configuration, with a state key and a variables file per environment, in the existing state bucket with native lockfile locking. Role ARNs come in as variables and are only passed on.
- **The functions:** the build and extraction functions run the same image digest from the shared ECR repository (ADR 0006). The build is limited to a concurrency of 1.
- **The schedule:** an EventBridge Scheduler job every 15 minutes, as a per-environment variable, using the scheduler role.
- **The working bucket:** `snacker-tracker-<env>-*`, holding the products table and the Snacker archive.
- **CloudFront:**
  - The origin is the site bucket's website endpoint.
  - It serves `staging.<domain>`, with an ACM certificate (us-east-1) validated through the Route 53 zone, and an alias record.
  - It respects each object's `Cache-Control`.
  - Deep links fall back to `index.html`. The frontend already treats an HTML reply for a data file as missing.
- **Staging's data:** it reads production's raw events, read-only.
- **No alerting** for now. A failing build shows in "Data built X ago" and the function's logs.

- [ ] Applied by hand with the staging CI role's credentials, it creates everything without any IAM write.
- [ ] Within 15 minutes of applying, `staging.<domain>` serves the frontend and data built by the Lambda, and the scanners page's "Data built X ago" stays current.
- [ ] A scanned code missing from the products table triggers an extraction, and a later build names the product.
- [ ] `/codes/…` deep links load.

## Comments

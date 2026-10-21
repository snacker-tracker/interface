# 06: Dev runs on Lambda behind CloudFront

**What to build:** a working dev environment. Every 15 minutes a Lambda builds the data from dev's raw events (`snacker-tracker-dev`), and the dev site serves it with the frontend through CloudFront on `dev.khanom.xyz`.

**Blocked by:** 04 (One container image), 05 (Admin Terraform).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0003–0006):

- **The main configuration, applied by CI:** one configuration, with environments as Terraform workspaces (`dev`, `prod`).
  - **State:** in `snacker-tracker-aws-infra-tfstate` under its own key, so each workspace's state is at `env:/<workspace>/<main key>`, with native lockfile locking.
  - **Names:** every resource name comes from `snacker-tracker-${terraform.workspace}-`.
  - **Per-environment values** come from `<workspace>.tfvars`.
  - **Role ARNs** come in as variables and are only passed on.
- **The functions:** the build and extraction functions run the same image digest from the shared ECR repository (ADR 0006). The build is limited to a concurrency of 1.
- **The schedule:** an EventBridge Scheduler job every 15 minutes, as a per-environment variable, using the scheduler role.
- **The working bucket:** `snacker-tracker-${terraform.workspace}-…`, holding the products table and the Snacker archive.
- **CloudFront:**
  - The origin is the private site bucket (its REST endpoint), through an Origin Access Control. The bucket's policy, from the admin configuration, already admits CloudFront from this account.
  - Deep links: 403 and 404 replies map to `/index.html` with status 200.
  - It serves `dev.khanom.xyz`, with an ACM certificate (us-east-1) validated through the `khanom.xyz` zone (`Z0781732PCOBWRVFR9YS`), and A/AAAA alias records.
  - It respects each object's `Cache-Control`.
  - Deep links fall back to `index.html`. The frontend already treats an HTML reply for a data file as missing.
- **Raw events:** each environment reads only its own raw scanner bucket, read-only: dev reads `snacker-tracker-dev`, and prod reads `snacker-tracker-prod`. Both buckets exist already, and Terraform doesn't manage them.
- **No alerting** for now. A failing build shows in "Data built X ago" and the function's logs.

- [ ] Applied by hand in the `dev` workspace with the dev CI role's credentials, it creates everything without any IAM write, and every resource name carries `dev`.
- [ ] Within 15 minutes of applying, `dev.khanom.xyz` serves the frontend and data built by the Lambda, and the scanners page's "Data built X ago" stays current.
- [ ] A scanned code missing from the products table triggers an extraction, and a later build names the product.
- [ ] `/codes/…` deep links load.

## Comments

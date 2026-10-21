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

### 2026-10-21: dev applied; the CI policy needs one admin fix; extraction trigger untested (dev has no scans)

`infra/main/`, applied in `dev` **with admin credentials** (agreed with the user). The CI role's trust admits only GitHub OIDC, so its permissions were checked with the IAM policy simulator instead. **15 resources:**
- the two functions, on image `…/snacker-tracker-lambda/interface@sha256:819552e5…` (commit `d4eb6ce`, pushed with `backend/scripts/push-image.sh`);
- the extraction's async-invoke settings (no retries);
- the schedule `rate(15 minutes)`, two log groups (30 days) and `snacker-tracker-dev-working`;
- the OAC, the distribution `E231M2LQCSNTS7` (403/404 → `/index.html` 200, CachingOptimized), the us-east-1 certificate with its validation record, and A/AAAA aliases for `dev.khanom.xyz`.

**Decisions (agreed with the user):**
- **No reserved concurrency of 1 on the build:** the account's Lambda limit is 10, and AWS keeps all 10 unreserved. Add it back after a quota increase.
- **First apply as admin, with the CI role simulated.**
- **Dev's only raw scan was a hand-made test event,** deleted: code `321321321`, location `montreal`, `scanned_at` `…+07`. The strict build rejected its offset, and it had no office time zone. Dev now holds one valid heartbeat and no scans.

**By hand after the apply:** uploaded `data/codes.csv` as `snacker-archive.csv`. Synced `frontend/dist` outside `data/`: hashed assets `max-age=31536000, immutable`, `index.html` `no-cache`.

**Checked through CloudFront:**
- `/`: 200, HTML.
- `/codes/8851959132012`: 200, `index.html` (the deep link loads).
- `/data/meta.json`: JSON, `max-age=60`.
- A missing data file: `index.html`.
- HTTP: 301 to HTTPS.

**The function, invoked once:** `uploaded 4, deleted 3462; extraction not needed`. The deletes were the earlier test build. It took 6.5 s and 194 MB of 2,048, with a 1.8 s cold start, and `generated_at` moved to `06:58:33Z`. The schedule fires every 15 minutes: the logs show the failed runs before the test scan was removed.

**CI role, simulated for the actions this apply used:**
- **Allowed:** Lambda create and update, PassRole (to Lambda and Scheduler), ECR pull, Scheduler, logs, the working bucket, reading the site bucket, updating the tagged distribution, describing the tagged certificate, Route 53 changes to `dev.khanom.xyz` and `_….dev.khanom.xyz`, and its state and lock.
- **Denied, as intended:** Route 53 changes to `khanom.xyz` and `reporter-dev.khanom.xyz`.
- **Denied by mistake:** `cloudfront:CreateDistribution`, `cloudfront:CreateOriginAccessControl`, `acm:RequestCertificate` and `acm:AddTagsToCertificate`. These take only `Resource: "*"`, and ticket 05 had scoped them to ARNs. Fixed in `infra/admin/ci_role.tf`: `"*"`, keeping the `aws:RequestTag/project` condition (none for OAC, which can't be tagged). Planned (1 policy, in place, Access Analyzer clean). **Admin apply pending.**

**Open:**
- **Acceptance "a missing code triggers an extraction":** this needs a scan in dev, and dev has none until a real dev scanner sends one. The build role's `lambda:InvokeFunction` on `snacker-tracker-dev-extract` is in its policy but not yet exercised.
- **Build memory:** 2,048 MB is far above the 194 MB used, and could drop to 512–1,024.

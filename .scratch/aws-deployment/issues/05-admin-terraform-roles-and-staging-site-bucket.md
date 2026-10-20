# 05: Admin Terraform: roles and the staging site bucket

**What to build:** the Terraform configuration an admin applies by hand. It creates every IAM role and the staging site bucket, so that CI later never creates or alters a permission (ADR 0005).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0004–0006):

- **Per environment** (staging and production), each role limited to `snacker-tracker-<env>-*` and the tag `project=snacker-tracker`:
  - **CI role:** trusted only for GitHub OIDC from this repo's matching GitHub environment, plus pull requests for plans.
    - It can manage Lambda, Scheduler and the working bucket within its prefix.
    - It can only create CloudFront distributions and ACM certificates with the project tag, and only change or delete ones that carry it.
    - In Route 53 it can only change records in the one hosted zone.
    - It can read and write only its own key and lockfile in the existing state bucket.
    - In its site bucket it can put and delete objects anywhere except `data/*`, which is an explicit deny.
    - **IAM:** only `GetRole`, and `PassRole` for its environment's three roles to `lambda.amazonaws.com` and `scheduler.amazonaws.com`.
    - **ECR:** staging's role can push to the shared repository. Production's can only read it.
  - **Build role:** read the raw bucket's scanner prefix, read the products table, list and put/delete under `data/` in its site bucket only, invoke its extraction function, and write its own logs.
  - **Extraction role:** read the Snacker archive and write the products table in its working bucket, and write its own logs.
  - **Scheduler role:** invoke its build function only.
- **The staging site bucket:** a website bucket with a public-read policy and default S3 encryption (SSE-S3, ADR 0004). The production site bucket and the raw bucket already exist and aren't touched.
- **Variables and outputs:** inputs are the existing bucket names, the hosted zone, the ECR repository ARN, the state bucket and the GitHub repo. The role ARNs are outputs.
- **Out of scope:** alerting.

- [ ] The admin configuration plans and applies cleanly in the account, and outputs the role ARNs for both environments.
- [ ] No policy grants any IAM write action. `PassRole` is limited to the known roles and services.
- [ ] Each CI role's trust allows only its own GitHub environment (and pull requests for plans).
- [ ] The README of the infrastructure directory says who applies it and when: whenever a permission must change.

## Comments

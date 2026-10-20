# 05: Admin Terraform: roles and the dev site bucket

**What to build:** the Terraform configuration an admin applies by hand. It creates every IAM role and the dev site bucket, so that CI later never creates or alters a permission (ADR 0005).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0004–0006):

- **Environments are Terraform workspaces:** `dev` and `prod`. State lives in `snacker-tracker-aws-infra-tfstate`, under the admin configuration's own key, so each workspace's state sits at `env:/<workspace>/<admin key>`.
  - Names come from the workspace: `snacker-tracker-${terraform.workspace}-*`.
  - Per-environment values come from a `<workspace>.tfvars` file.
  - The CI roles get no access to the admin configuration's state.
- **Per environment** (one workspace each), each role limited to `snacker-tracker-<env>-*` and the tag `project=snacker-tracker`:
  - **CI role:** trusted only for GitHub OIDC from this repo's matching GitHub environment, plus pull requests for plans.
    - It can manage Lambda, Scheduler and the working bucket within its prefix.
    - It can only create CloudFront distributions and ACM certificates with the project tag, and only change or delete ones that carry it.
    - In Route 53 it can only change records in the `khanom.xyz` zone (`Z0781732PCOBWRVFR9YS`), and only its own environment's names and their ACM validation records (`_*.<name>`), using the normalised-record-names condition. Dev owns `dev.khanom.xyz`; prod owns `khanom.xyz` and `www.khanom.xyz`.
    - In `snacker-tracker-aws-infra-tfstate`, it can read and write only the main configuration's state for its own workspace, `env:/<env>/<main key>` and its lockfile, and list the bucket only under that prefix.
    - In its site bucket it can put and delete objects anywhere except `data/*`, which is an explicit deny.
    - **IAM:** only `GetRole`, and `PassRole` for its environment's three roles to `lambda.amazonaws.com` and `scheduler.amazonaws.com`.
    - **ECR:** dev's role can push to the shared repository. Prod's can only read it.
  - **Build role:** read its own environment's raw scanner bucket (`snacker-tracker-dev` or `snacker-tracker-prod`), read the products table, list and put/delete under `data/` in its site bucket only, invoke its extraction function, and write its own logs.
  - **Extraction role:** read the Snacker archive and write the products table in its working bucket, and write its own logs.
  - **Scheduler role:** invoke its build function only.
- **Raw buckets:** `snacker-tracker-dev` and `snacker-tracker-prod` exist already and aren't managed here. The CI roles' prefix rights (`snacker-tracker-<env>-*`, hyphen included) don't match them, and an explicit deny keeps the CI roles out of them anyway.
- **The dev site bucket** (dev workspace only): a website bucket with a public-read policy and default S3 encryption (SSE-S3, ADR 0004). The prod site bucket already exists and isn't touched.
- **Variables and outputs:** inputs are the existing bucket names, the hosted zone (`khanom.xyz`, `Z0781732PCOBWRVFR9YS`), each environment's hostnames, the ECR repository ARN and the GitHub repo. The role ARNs are outputs, per workspace.
- **Out of scope:** alerting.

- [ ] The admin configuration plans and applies cleanly in both the `dev` and `prod` workspaces, and each workspace outputs its role ARNs.
- [ ] No policy grants any IAM write action. `PassRole` is limited to the known roles and services.
- [ ] Each CI role's trust allows only its own GitHub environment (and pull requests for plans).
- [ ] The README of the infrastructure directory says who applies it and when: whenever a permission must change.

## Comments

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
- **The site bucket** (each workspace, `snacker-tracker-<env>-site`): private, with default S3 encryption (SSE-S3, ADR 0004). Its policy lets only CloudFront from this account read it, through Origin Access Control. (Changed 2026-10-20: account-wide Block Public Access rules out a public website bucket, and no prod site bucket existed.)
- **The ECR repository** (dev workspace only, `snacker-tracker-lambda/interface`): created here until it moves to the repo that manages shared infrastructure (ADR 0006). Its policy lets Lambda pull, so the CI roles never need `ecr:SetRepositoryPolicy`.
- **Variables and outputs:** inputs are the existing bucket names, the hosted zone (`khanom.xyz`, `Z0781732PCOBWRVFR9YS`), each environment's hostnames, the ECR repository ARN and the GitHub repo. The role ARNs are outputs, per workspace.
- **Out of scope:** alerting.

- [ ] The admin configuration plans and applies cleanly in both the `dev` and `prod` workspaces, and each workspace outputs its role ARNs.
- [ ] No policy grants any IAM write action. `PassRole` is limited to the known roles and services.
- [ ] Each CI role's trust allows only its own GitHub environment (and pull requests for plans).
- [ ] The README of the infrastructure directory says who applies it and when: whenever a permission must change.

## Comments

### 2026-10-20: dev applied

`infra/admin/`. **Applied in `dev`: 21 resources.** **`prod` is planned (19 resources) but not applied yet.** A re-plan in dev shows no changes.

Outputs (dev):
- `ci_role_arn = arn:aws:iam::132218943709:role/snacker-tracker-dev-ci`
- `build_role_arn = …:role/snacker-tracker-dev-build`, `extraction_role_arn = …:role/snacker-tracker-dev-extraction`, `scheduler_role_arn = …:role/snacker-tracker-dev-scheduler`
- `site_bucket = snacker-tracker-dev-site` (SSE-S3, all four Block Public Access settings on)
- `ecr_repository_url = 132218943709.dkr.ecr.ap-southeast-1.amazonaws.com/snacker-tracker-lambda/interface`

**Decisions made while building it (agreed with the user):**
- **The site buckets are private, behind Origin Access Control.** Account-wide S3 Block Public Access is on (`BlockPublicPolicy`, `RestrictPublicBuckets`), so a public-read website bucket can't work. Each bucket's policy lets `cloudfront.amazonaws.com` read, with `AWS:SourceAccount` set to this account (the distribution is created later, by the main configuration).
- **No prod site bucket existed.** The prod workspace creates `snacker-tracker-prod-site`. Tickets 06 and 08 and ADR 0005 are updated to match.
- **The ECR repository is created here, in dev only,** until it moves out (ADR 0006 has a note). Its policy lets Lambda pull from `snacker-tracker-*` functions, so CI never needs `ecr:SetRepositoryPolicy`.
- **GitHub repo:** `snacker-tracker/interface`.

**Where it goes beyond the ticket's wording:**
- **The extraction role also reads the raw bucket and the products table.** Today the extraction takes its codes from the raw scans (`--raw`), and it skips a table that already covers them. If 04 has the build pass the codes instead, the raw read can go.
- **State listing:** the S3 backend lists `env:/` to find workspaces, so the CI role can list that prefix (other configurations' key names, but not their contents) as well as its own key.
- **The CI role can manage `/aws/lambda/snacker-tracker-<env>-*` log groups,** so the main configuration can set retention.
- **Origin access controls can't carry tags,** so the CI role can manage any of them. They grant nothing by themselves: the bucket policy decides.
- **No `lambda:AddPermission` or function URLs:** those are resource policies, and nothing needs them.
- **The CI policies are three managed policies** (`-ci-workloads`, `-ci-edge`, `-ci-guards`), not inline ones, because of the 10 KB inline limit per role.
- **Names the main configuration must use:** working bucket `snacker-tracker-<env>-working` with `products.parquet` and `snacker-archive.csv`, functions `-build` and `-extract`, state key `snacker-tracker-interface`. They're listed in the README.

**Checks:**
- **Access Analyzer `validate-policy`:** every policy is clean except two expected findings. The ECR repository policy is flagged for having no Resource, which repository policies don't have. The OIDC trust gets a warning that the subject has no branch, but it is meant to be environment-based.
- **IAM policy simulator, dev CI role:**
  - **Allowed:** put `index.html` in the site bucket, create the working bucket, `PassRole` build→Lambda, update dev's functions, write its own state, push to ECR.
  - **Explicit deny:** put `data/meta.json`, read the `snacker-tracker-dev` raw bucket, `PutBucketPolicy`.
  - **Implicit deny:** `CreateRole`, `PutRolePolicy` on itself, `PassRole` to EC2, prod's functions, `AddPermission`, the admin state, prod's state.
- **Not yet tested for real:** the CloudFront and ACM tag conditions and the Route 53 record-name condition. Ticket 06's first plan under the CI role will exercise them. Anything missing there means an admin re-apply.

**2026-10-21: prod applied.** `infra/admin`, prod workspace: 19 created, nothing changed. Before applying, the prod CI role's trust was narrowed to `environment:prod` only; only dev's role trusts `pull_request`.

**Checked after the apply:**
- `snacker-tracker-prod-site` uses AES256 and blocks all public access.
- The IAM simulator on `snacker-tracker-prod-ci`:
  - allowed: frontend writes, image pulls, and its own state `env:/prod/…`;
  - explicitly denied: `data/*` and the raw buckets;
  - not granted: `ecr:PutImage` and dev's state.

# Admin configuration

Everything CI must not be able to create or change itself (ADR 0005): every IAM role and
policy, the site buckets and their policies, and for now the shared ECR repository (ADR 0006).

## Who applies it, and when

An admin with IAM rights applies it **by hand**, never CI, whenever a permission must change:
- a function needs more access;
- the main configuration starts managing a new kind of resource;
- a new environment or hostname is added.

Until then, the main configuration's plan fails with an access error. That's expected: it means
an admin apply comes first.

```sh
terraform init
terraform workspace select -or-create dev     # or prod
terraform plan -var-file=dev.tfvars -out=dev.tfplan
terraform apply dev.tfplan
```

Read the plan before applying: every policy is shown in full.

## What it creates, per workspace

Names come from the workspace: `snacker-tracker-<env>-*`.

| Resource | For |
| --- | --- |
| `snacker-tracker-<env>-ci` role | The main configuration's applies. Trusted only for GitHub OIDC from this repo's `<env>` GitHub environment, and pull requests (for plans). |
| `snacker-tracker-<env>-build` role | The build function: reads the raw bucket and the products table, publishes `data/`, starts the extraction. |
| `snacker-tracker-<env>-extraction` role | The extraction function: reads the raw scans, the Snacker archive and the products table, writes the products table. |
| `snacker-tracker-<env>-scheduler` role | The schedule: invokes the build. |
| `snacker-tracker-<env>-site` bucket | The frontend and `data/`. Private, SSE-S3 (ADR 0004); CloudFront reads it through Origin Access Control. |
| ECR `snacker-tracker-lambda/interface` (dev only) | The backend image, until it moves to the repo that manages shared infrastructure. |

## Names the main configuration must use

The policies are written against these, so the main configuration has to create them under exactly these names:
- the working bucket `snacker-tracker-<env>-working`, holding `products.parquet` and `snacker-archive.csv`;
- the functions `snacker-tracker-<env>-build` and `snacker-tracker-<env>-extract`;
- the schedule `snacker-tracker-<env>-*` in the default group;
- the state key `snacker-tracker-interface` (so `env:/<env>/snacker-tracker-interface`).

CloudFront distributions and ACM certificates must carry the tag `project=snacker-tracker`.
The provider's `default_tags` does that.

## State

The state is in `snacker-tracker-aws-infra-tfstate` at `env:/<workspace>/snacker-tracker-interface-admin`.
The CI roles have no access to it.

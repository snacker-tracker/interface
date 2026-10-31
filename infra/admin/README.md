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
| `snacker-tracker-<env>-scheduler` role | The schedules: invokes the build, and starts the graph's state machine. |
| `snacker-tracker-<env>-site` bucket | The frontend and `data/`. Private, SSE-S3 (ADR 0004); CloudFront reads it through Origin Access Control. |
| `snacker-tracker-<env>-access-logs` bucket | The distribution's access logs, under `cloudfront/` (ADR 0010). Private, SSE-S3, expires objects after 90 days. Only this environment's log delivery sources may write to it. |
| `snacker-tracker-<env>-access-log-delivery` CloudWatch Logs resource policy (us-east-1) | Lets log delivery write to log groups under `/aws/vendedlogs/cloudfront/snacker-tracker-<env>-*`, so CI never needs to add a resource policy (ADR 0010). |
| `snacker-tracker-<env>-graph-<role>` roles | The stepdag graph's functions (`graph.tf`), one per manifest role: read the raw events of `graph_raw_bucket` (prod's, in dev too), read and write `tables/` and `files/` in the working bucket, read the Snacker archive, publish the shadow bucket's `data/`. |
| `snacker-tracker-<env>-graph-state-machine` role | The graph's state machine: invokes `snacker-tracker-<env>-graph-*` functions. |
| `snacker-tracker-<env>-shadow` bucket | The graph's site tree until the switchover (#124). Private, SSE-S3. |
| ECR `snacker-tracker-lambda/interface` (dev only) | The backend image, until it moves to the repo that manages shared infrastructure. |

## Names the main configuration must use

The policies are written against these, so the main configuration has to create them under exactly these names. The graph's roles come from the manifest the main configuration deploys (`../main/graph.manifest.json`), so render it before planning here when an asset's role changes.

The CI roles that apply the main configuration are managed in `snacker-tracker/aws-infra`; a new kind of resource there is a change to that repo too, as the graph's state machine was.
- the working bucket `snacker-tracker-<env>-working`, holding `products.parquet`, `snacker-archive.csv` and the event cache under `cache/` (ADR 0011);
- the functions `snacker-tracker-<env>-build` and `snacker-tracker-<env>-extract`, and the graph's `snacker-tracker-<env>-graph-<asset>`;
- the graph's state machine `snacker-tracker-<env>-graph`, and its tables and copies under `tables/` and `files/` in the working bucket;
- the schedule `snacker-tracker-<env>-*` in the default group;
- the state key `snacker-tracker-interface` (so `env:/<env>/snacker-tracker-interface`);
- in us-east-1, the access-log group `/aws/vendedlogs/cloudfront/snacker-tracker-<env>-*`, and the delivery sources and destinations `snacker-tracker-<env>-*`. Deliveries to the bucket write under its `cloudfront/` prefix.

CloudFront distributions and ACM certificates must carry the tag `Project=snacker-tracker`.
The provider's `default_tags` does that.

## State

The state is in `snacker-tracker-aws-infra-tfstate` at `env:/<workspace>/snacker-tracker-interface-admin`.
The CI roles have no access to it.

# The graph on Step Functions, applied by hand (dev)

A temporary stack: the graph (`snacker.graph`) as it ran while it was the stepdag scans example.
#121 replaces it with the graph in `infra/admin` and `infra/main`, deployed by CI, and destroys this.

Applied by hand, never CI. State: `env:/dev/stepdag-scans` in `snacker-tracker-aws-infra-tfstate`.
Names: `stepdag-scans-dev-*`, except the functions, `snacker-tracker-dev-graph-*`: the shared
repository lets Lambda pull only for functions named `snacker-tracker-*`. Region `ap-southeast-1`.

Every function runs the one Lambda image (`backend/Dockerfile`), which CI builds for each commit
into the shared repository (ADR 0006), tagged with the commit SHA. Terraform sets each function's
handler from the manifest. The functions read Snacker's prod raw scanner events
(`s3://snacker-tracker-prod/raw/data/scanner/`, read-only) and write Delta tables to
`s3://stepdag-scans-dev-tables`. `site_tree` publishes Snacker's tree into the private shadow
bucket `s3://stepdag-scans-dev-site` (`data/`). EventBridge Scheduler starts the state machine
every 30 minutes with `{}` and daily at 03:00 Asia/Bangkok with `{"download": true}`
(`-var schedules_enabled=false` disables both). Toggle schedules only through that variable: a
change made in the console is undone by the next apply.

The `stepdag-scans` ECR repository is left over from the example, which built its own image; it's
unused since #118 and goes with the stack.

## 1. Render the manifest

```sh
cd backend
uv run stepdag manifest snacker.graph.definitions:defs > ../infra/stepdag-scans-dev/manifest.json
uv run pytest tests/graph/test_manifest.py     # passes once it's fresh
```

## 2. Apply a commit's image

After the commit's pipeline has pushed its image:

```sh
cd infra/stepdag-scans-dev
SHA=$(git rev-parse HEAD)
DIGEST=$(aws ecr describe-images --repository-name snacker-tracker-lambda/interface \
  --image-ids imageTag="$SHA" --query 'imageDetails[0].imageDigest' --output text)
REPO=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-southeast-1.amazonaws.com/snacker-tracker-lambda/interface
terraform init
terraform workspace select dev
terraform plan -var image_uri="$REPO@$DIGEST" -out=scans.tfplan   # review it
terraform apply scans.tfplan
SM=$(terraform output -raw state_machine_arn)
TABLES=$(terraform output -raw tables_bucket)
```

`products` reads Snacker's archive from `s3://stepdag-scans-dev-tables/snacker-archive.csv`, copied
by hand once from `s3://snacker-tracker-prod-working/snacker-archive.csv`; copy it again only if
the tables bucket is recreated.

A forced run rebuilds every table from raw (about 13 minutes, most of it `heartbeats`):

```sh
aws stepfunctions start-execution --state-machine-arn "$SM" --name "forced-$(date +%H%M)" --input '{"force": true}'
```

## Parity reports

Each run's `parity` report is at `s3://$TABLES/json/runs/<run>/parity.json` (`<run>` is the
execution name; a scheduled run's is a generated ID), as a pointer whose `value` holds
`{identical, only_ours, only_snackers, differing}`. The shadow tree is under
`s3://$(terraform output -raw site_bucket)/data/`.

```sh
aws s3 ls "s3://$TABLES/json/runs/" --recursive | grep parity.json | sort | tail -3   # newest last
aws s3 cp "s3://$TABLES/json/runs/<run>/parity.json" - | jq .value
```

## Inspect the tables

Each Delta asset is a table at `s3://$TABLES/<asset>`. From `backend/`:

```sh
TABLES=$TABLES uv run python -c '
import os, polars as pl
from deltalake import DeltaTable
uri = f"s3://{os.environ[\"TABLES\"]}/scans"
print(DeltaTable(uri).version(), pl.scan_delta(uri).select(pl.len()).collect().item())
'
```

## Tear down

```sh
terraform destroy -var image_uri="$REPO@$DIGEST"
```

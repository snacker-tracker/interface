# The scans example on Step Functions (dev)

Applied by hand, never CI. State: `env:/dev/stepdag-scans` in `snacker-tracker-aws-infra-tfstate`.
Names: `stepdag-scans-dev-*`, and the ECR repository `stepdag-scans`. Region `ap-southeast-1`.

Every function runs one container image (`../Dockerfile`): stepdag, the example, Snacker's package
(`backend/`) and their third-party dependencies. Terraform sets each function's handler from the manifest. The functions read
Snacker's prod raw scanner events (`s3://snacker-tracker-prod/raw/data/scanner/`, read-only) and
write Delta tables to `s3://stepdag-scans-dev-tables`. `site_tree` publishes Snacker's tree into the
private shadow bucket `s3://stepdag-scans-dev-site` (`data/`). EventBridge Scheduler starts the state
machine every 30 minutes with `{}` and daily at 03:00 Asia/Bangkok with `{"download": true}`
(`-var schedules_enabled=false` disables both).

## 1. Render the manifest

```sh
cd stepdag/examples/scans
uv run stepdag manifest scans_example.graph:defs > infra/manifest.json
uv run pytest tests/test_manifest.py     # passes once it's fresh
```

## 2. Create the repository

```sh
cd infra
terraform init
terraform workspace select -or-create dev
terraform apply -target=aws_ecr_repository.scans
REPO=$(terraform output -raw repository_url)
```

Without an image the functions refuse to plan (`image_uri` must be set), so this is the only
apply that works before step 3.

## 3. Build and push the image (the person with docker)

From the repo root, the build context (it holds `backend/` and `stepdag/`; the root `.dockerignore`
keeps it to what the Dockerfile copies):

```sh
cd "$(git rev-parse --show-toplevel)"
docker build --platform linux/amd64 --provenance=false -f stepdag/examples/scans/Dockerfile -t stepdag-scans .
aws ecr get-login-password --region ap-southeast-1 \
  | docker login --username AWS --password-stdin "${REPO%%/*}"
docker tag stepdag-scans "$REPO:latest"
docker push "$REPO:latest"
DIGEST=$(aws ecr describe-images --region ap-southeast-1 --repository-name stepdag-scans \
  --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text)
echo "$REPO@$DIGEST"
```

`--provenance=false` keeps the push a single-platform manifest, which Lambda requires.

## 4. Copy the Snacker archive (once)

`products` reads Snacker's archive from `$SCANS_ARCHIVE`, `s3://stepdag-scans-dev-tables/snacker-archive.csv`.
Copy it by hand, with credentials that can read Snacker's prod working bucket, so Terraform and the
functions never need access to it. The tables bucket must exist first
(`terraform apply -target=aws_s3_bucket.tables`), or copy it after step 5 and before the first run.

```sh
aws s3 cp s3://snacker-tracker-prod-working/snacker-archive.csv s3://stepdag-scans-dev-tables/snacker-archive.csv
```

## 5. Apply

```sh
cd stepdag/examples/scans/infra
terraform plan -var image_uri="$REPO@$DIGEST" -out=scans.tfplan   # one Lambda per manifest function
terraform apply scans.tfplan
SM=$(terraform output -raw state_machine_arn)
TABLES=$(terraform output -raw tables_bucket)
```

A new image means a new digest: push, then plan and apply again with it.

The schedules start runs as soon as they're applied. The first deployed run after parity work must
be forced, since the deployed `scans` table lacks `api_key` and earlier tables' schemas changed (a
merge never changes a schema). Apply with `-var schedules_enabled=false`, run this, then apply again
without it:

```sh
aws stepfunctions start-execution --state-machine-arn "$SM" --name parity-first --input '{"force": true}'
```

## Parity reports

Each run's `parity` report is at `s3://$TABLES/json/runs/<run>/parity.json` (`<run>` is the
execution name; a scheduled run's is a generated ID). The shadow tree is under
`s3://$(terraform output -raw site_bucket)/data/`.

```sh
aws s3 ls "s3://$TABLES/json/runs/" --recursive | grep parity.json | sort | tail -3   # newest last
aws s3 cp "s3://$TABLES/json/runs/<run>/parity.json" - | jq .
```

## 6. Run the acceptance executions (ticket 06)

Run them in order, waiting for each to finish (`aws stepfunctions describe-execution --execution-arn … --query status`):

```sh
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-1 --input '{}'   # full build
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-2 --input '{}'   # nothing new: scans skipped
# wait for new scans to arrive under raw/data/scanner/, then:
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-3 --input '{}'   # merges only the new scans
aws stepfunctions start-execution --state-machine-arn "$SM" --name run-4 --input '{"force": true}'   # rebuilds everything
```

## 7. Inspect the tables

Each asset is a Delta table at `s3://$TABLES/<asset>`. Row counts and the latest version, from
`stepdag/examples/scans`:

```sh
TABLES=$TABLES uv run python -c '
import os, polars as pl
from deltalake import DeltaTable
uri = f"s3://{os.environ[\"TABLES\"]}/scans"
print(DeltaTable(uri).version(), pl.scan_delta(uri).select(pl.len()).collect().item())
print(pl.scan_delta(uri).head(5).collect())
'
```

Commits and data files (a skipped run adds neither; a forced one adds both):

```sh
aws s3 ls "s3://$TABLES/scans/_delta_log/" --recursive | grep -c '\.json$'
aws s3 ls "s3://$TABLES/scans/" --recursive | grep -c '\.parquet$'
aws s3 ls "s3://$TABLES/"      # one prefix per asset
```

Write the results in ticket 06's comments.

## Tear down

```sh
terraform destroy -var image_uri="$REPO@$DIGEST"
```

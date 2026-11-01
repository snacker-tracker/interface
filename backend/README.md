# snacker (backend)

Turns raw scanner events into the static JSON read by the frontend, as a stepdag graph
(`snacker.graph.definitions:defs`, #117): raw events into Delta tables, then each section of the
site, then the whole tree, checked and published. `infra/main` (`graph.tf`) deploys it as one
Lambda per asset in a Step Functions workflow, run every 30 minutes.

See `PRD.md` at the repo root for the data contract. Its shapes are defined in
`src/snacker/contract.py`; after changing them, rerun `snacker schema` to update the
committed JSON Schema (a test fails until you do).

```sh
scripts/build-local-data.sh                   # the graph over ../data, into ../public-data/data/
uv run snacker check --out ../public-data     # the graph already does this
uv run snacker schema --out ../contract/static-json.schema.json
uv run pytest
uv run mypy
```

After changing an asset, render the manifest that `infra/main` and `infra/admin` read:

```sh
uv run stepdag manifest snacker.graph.definitions:defs > ../infra/main/graph.manifest.json
```

## Running the graph locally

`scripts/build-local-data.sh` runs `stepdag run snacker.graph.definitions:defs` with the local
bindings. The assets take their settings from the environment, which the script defaults to
`../data`:

| Variable | Default | What |
| --- | --- | --- |
| `SCANS_RAW` | `../data/raw/data/scanner` | The raw events, or an `s3://` prefix |
| `SCANS_OPENFOODFACTS` | `../data/openfoodfacts__product-database/food.parquet` | OpenFoodFacts's `food.parquet`, or `hf` |
| `SCANS_ARCHIVE` | `../data/codes.csv` | The Snacker archive: names for products OpenFoodFacts can't name |
| `SCANS_TABLES` | `../data/tables` | The Delta tables, and the JSON IO manager's values under `json/` |
| `SCANS_FILES` | `../data/files` | Where the OpenFoodFacts copy goes |
| `SCANS_SITE` | `../public-data` | Where `data/` is published, or `s3://<site bucket>` |
| `SCANS_OFFICE_TIME_ZONES` | `src/snacker/config.py`'s | JSON, for tests |

Extra arguments go to `stepdag run`: `--force` reads every raw file again and rebuilds every
table, and `--select <asset> --downstream` runs part of the graph. The tables persist, so a later
run reads only the raw files modified since the newest one it has read, less 15 minutes (ADR
0011): Firehose names a file for its buffer's start but writes it when the buffer closes. The
first run copies `food.parquet` (8 GB) into `SCANS_FILES`; later ones copy it again only when
asked for a download (`--config '{"download": true}'`) and the revision is new.

Office time zones live in `src/snacker/config.py`: a map from location prefix to IANA
time zone, where the longest prefix wins. A scanned location with no match fails the run at
`scanned`, so add a line there when a scanner goes into a new office.

`site_tree` checks the whole tree against the output contract (PRD.md §7) before publishing it:
if any file breaks it, the run fails with each violation and the previous `data/` stays as it was.

## Publishing to S3

With `SCANS_SITE=s3://<site bucket>`, publishing touches only `data/` (ADR 0004):

- It uploads the files whose MD5 differs from the object's ETag, with
  `Content-Type: application/json` and `Cache-Control: max-age=60`.
- It deletes the `data/` keys the tree no longer has.
- It writes `meta.json` last.
- **The site bucket must use default S3 encryption (SSE-S3), not KMS.** With SSE-KMS an ETag
  isn't the file's MD5, so every file would look changed and be uploaded on every run.

## The Lambda image

One image runs every function (`Dockerfile`, Python 3.14 on the AWS Lambda base image):
`stepdag.aws.plan_handler` plans a run, and `stepdag.aws.asset_handler` runs one asset's step,
named by `STEPDAG_ASSET`. Terraform sets each function's handler, sizes and environment from
the manifest, and the `SCANS_*` settings above from `graph.tf`.

`scripts/push-image.sh` pushes the image for the current commit to the shared ECR repository,
tagged with the short commit SHA (and in CI with its version, `MAJOR.MINOR.<run number>` from
`pipeline.yml`), and prints its URI by digest. That URI is what the main Terraform configuration
takes as `image_uri`. A commit that already has an image reuses it. The image's labels name its
commit, version, build time and, in CI, the run that built it (`docker inspect`, or the image's
config in ECR). Each deploy adds an `<environment>-<UTC time>` tag, which the repository's
lifecycle rules keep (ADR 0006).

## Deploying

`.github/workflows/pipeline.yml` runs on every push to `master`:

1. Backend and stepdag tests and mypy, frontend lint and build. A failure stops everything before
   it starts.
2. `image`: `scripts/push-image.sh`, once per commit. The job summary records the digest.
3. `dev`, then `prod` once a reviewer approves the `prod` environment. Both run
   `.github/workflows/deploy.yml` with the same digest and frontend build:
   1. `terraform apply` of `infra/main` in the environment's workspace, which points every
      function at the digest, then tags the image as deployed there.
   2. `frontend/scripts/sync-site.sh`, which uploads `dist/` outside `data/`.

   The graph's next scheduled run publishes `data/` on the new image.

A pull request runs the same checks and puts a dev `terraform plan`, against the image dev runs
now, in its job summary. The plan takes no state lock. Only the dev CI role trusts pull requests.

**Rolling back:** open the pipeline run for the earlier commit and re-run its `prod / deploy` job.
It applies that commit's Terraform and promotes that commit's image and frontend build, after the
same approval. GitHub allows re-runs for 30 days, and the frontend build is kept for 90. Dev rolls
back the same way with `dev / deploy`; the next push to `master` deploys forward again.

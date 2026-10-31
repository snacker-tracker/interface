#!/usr/bin/env bash
# Build the Lambda image and run both handlers in the Lambda runtime emulator, against real S3.
#
# - Reads prod's raw events (read-only).
# - Writes the products table to a temporary scratch bucket, deleted at the end.
# - Publishes data/ to the dev site bucket.
#
# The extraction runs first, so the build finds every code covered and doesn't try to start the
# (not yet deployed) extraction function. Needs Docker, the AWS CLI and credentials in backend/.env.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; . ./.env; set +a
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"

tag="snacker-lambda:$(git rev-parse HEAD)"
docker build --platform linux/amd64 --provenance=false -f Dockerfile -t "$tag" ..
docker image ls "$tag" --format 'image {{.Repository}}:{{.Tag}} is {{.Size}}'

scratch="snacker-tracker-scratch-image-$(date +%s)"
aws s3 mb "s3://$scratch" >/dev/null
trap 'docker rm -f snacker-lambda >/dev/null 2>&1 || true; aws s3 rb --force "s3://$scratch" >/dev/null' EXIT
aws s3 cp --quiet ../data/codes.csv "s3://$scratch/snacker-archive.csv"

invoke() {
  local handler="$1"
  docker rm -f snacker-lambda >/dev/null 2>&1 || true
  docker run -d --name snacker-lambda --platform linux/amd64 -p 9000:8080 --memory 3g \
    -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION \
    -e AWS_LAMBDA_FUNCTION_TIMEOUT=900 \
    -e SNACKER_RAW=s3://snacker-tracker-prod/raw/data/scanner \
    -e SNACKER_PRODUCTS="s3://$scratch/products.parquet" \
    -e SNACKER_ARCHIVE="s3://$scratch/snacker-archive.csv" \
    -e SNACKER_SITE=s3://snacker-tracker-dev-site \
    -e SNACKER_EXTRACT_FUNCTION=snacker-tracker-dev-extract \
    "$tag" "$handler" >/dev/null
  sleep 2
  echo "== $handler"
  local start=$SECONDS
  curl -s http://localhost:9000/2015-03-31/functions/function/invocations -d '{}'
  echo
  echo "took $((SECONDS - start))s"
  docker logs snacker-lambda 2>&1 | grep -E 'Published|Looked up|REPORT|Error|Traceback' || true
}

invoke snacker.handlers.extract_handler
invoke snacker.handlers.build_handler

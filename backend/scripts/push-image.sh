#!/usr/bin/env bash
# Build the Lambda image and push it to the shared ECR repository, tagged with the commit SHA
# (ADR 0006). Prints the image URI by digest, which the main configuration's image_uri takes.
# Needs Docker, the AWS CLI and credentials in backend/.env. CI does this in ticket 07.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; . ./.env; set +a
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"

registry="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com"
repository="$registry/snacker-tracker-lambda/interface"
sha="$(git rev-parse HEAD)"
if [ -n "$(git status --porcelain -- .)" ]; then
  echo "backend/ has uncommitted changes; commit them so the tag matches what's built" >&2
  exit 1
fi

aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
# Lambda wants a single-platform image manifest, not an index with attestations.
docker build --platform linux/amd64 --provenance=false -t "$repository:$sha" .
docker push "$repository:$sha"
digest="$(aws ecr describe-images --repository-name snacker-tracker-lambda/interface \
  --image-ids imageTag="$sha" --query 'imageDetails[0].imageDigest' --output text)"
echo "image_uri = \"$repository@$digest\""

#!/usr/bin/env bash
# Build the Lambda image and push it to the shared ECR repository, tagged with the commit SHA
# (ADR 0006). Prints only the image URI by digest on stdout, which the main configuration's
# image_uri takes. An image already pushed for this commit is reused: tags are immutable, and
# each commit is built once. Needs Docker, the AWS CLI and AWS credentials, from backend/.env
# when it exists (CI has them from OIDC).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; . ./.env; set +a; fi
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"

repository_name=snacker-tracker-lambda/interface
registry="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com"
repository="$registry/$repository_name"
sha="$(git rev-parse HEAD)"
if [ -n "$(git status --porcelain -- . ../stepdag ../.dockerignore)" ]; then
  echo "backend/ or stepdag/ has uncommitted changes; commit them so the tag matches what's built" >&2
  exit 1
fi

digest() {
  aws ecr describe-images --repository-name "$repository_name" --image-ids imageTag="$sha" \
    --query 'imageDetails[0].imageDigest' --output text 2>/dev/null
}

if image_digest="$(digest)"; then
  echo "$repository:$sha is already pushed; reusing it" >&2
else
  aws ecr get-login-password | docker login --username AWS --password-stdin "$registry" >&2
  # Lambda wants a single-platform image manifest, not an index with attestations.
  # From the repo root, so the image can hold stepdag/ (the root .dockerignore trims the context).
  docker build --platform linux/amd64 --provenance=false -f Dockerfile -t "$repository:$sha" .. >&2
  docker push "$repository:$sha" >&2
  image_digest="$(digest)"
fi
echo "$repository@$image_digest"

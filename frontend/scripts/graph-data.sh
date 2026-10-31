#!/usr/bin/env bash
# Copy what the stepdag graph published to prod's site bucket (data/, #124) into ../graph-data, for
# `npm run dev:graph` to serve. Needs AWS credentials that can read prod's site bucket.
set -euo pipefail
cd "$(dirname "$0")/.."

out=../graph-data

aws s3 sync --delete s3://snacker-tracker-prod-site/data/ "$out/data/"
echo "the graph's data is in $out"

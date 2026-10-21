#!/usr/bin/env bash
# Upload the built frontend (dist/) to a site bucket, outside data/, which is the build's alone
# (ADR 0004). Hashed assets are cached for a year; everything else, index.html included, is
# revalidated on every request so a deploy shows at once. Old assets are deleted only after the
# new index.html is up, so a page loaded just before still finds its own. Nothing under data/ is
# touched.
#
#   scripts/sync-site.sh <site bucket>
set -euo pipefail
cd "$(dirname "$0")/.."
bucket="${1:?usage: scripts/sync-site.sh <site bucket>}"

# vite build copies ../public-data into dist/data/ when it exists locally; never upload it.
assets() { aws s3 sync dist/assets "s3://$bucket/assets" --cache-control "max-age=31536000, immutable" "$@"; }
assets
aws s3 sync dist "s3://$bucket" --delete \
  --exclude 'data/*' --exclude 'assets/*' \
  --cache-control "no-cache"
assets --delete

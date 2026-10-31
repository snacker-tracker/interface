#!/usr/bin/env bash
# Copy what the stepdag graph builds into ../graph-data, for `npm run dev:graph` to serve: the site
# data it published to prod's site bucket (data/), and its latest finished run (pipeline/latest.json,
# written by `stepdag report` from the run's execution history, #124). Needs AWS credentials that
# can read prod's site bucket and the graph's executions, and uv for the report.
set -euo pipefail
cd "$(dirname "$0")/.."

out=../graph-data
state_machine=arn:aws:states:ap-southeast-1:132218943709:stateMachine:snacker-tracker-prod-graph

aws s3 sync --delete s3://snacker-tracker-prod-site/data/ "$out/data/"
(cd ../backend && uv run stepdag report snacker.graph.definitions:defs \
  --state-machine "$state_machine" --out "../graph-data/pipeline/latest.json")
echo "graph data and its latest run are in $out"

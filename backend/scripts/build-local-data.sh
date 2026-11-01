#!/usr/bin/env bash
# Run the graph locally over the raw events in ../data, publishing the site's data into
# ../public-data/data/ for the frontend. Each setting can be overridden from the environment, and
# extra arguments go to `stepdag run` (e.g. --force, or --select code_pages --downstream).
#
# Its Delta tables and the OpenFoodFacts copy are kept in ../data, so a later run reads only new
# raw files, as in Lambda. The first run copies food.parquet (8 GB) into ../data/files/.
set -euo pipefail
cd "$(dirname "$0")/.."

export SCANS_RAW="${SCANS_RAW:-../data/raw/data/scanner}"
export SCANS_OPENFOODFACTS="${SCANS_OPENFOODFACTS:-../data/openfoodfacts__product-database/food.parquet}"
export SCANS_ARCHIVE="${SCANS_ARCHIVE:-../data/codes.csv}"
export SCANS_TABLES="${SCANS_TABLES:-../data/tables}"
export SCANS_FILES="${SCANS_FILES:-../data/files}"
export SCANS_SITE="${SCANS_SITE:-../public-data}"

uv run stepdag run snacker.graph.definitions:defs "$@"

# Snacker Tracker Interface

[![Maintainability](https://qlty.sh/gh/snacker-tracker/projects/interface/maintainability.svg)](https://qlty.sh/gh/snacker-tracker/projects/interface)
[![Code Coverage](https://qlty.sh/gh/snacker-tracker/projects/interface/coverage.svg)](https://qlty.sh/gh/snacker-tracker/projects/interface)

A read-only web interface showing which snacks are taken from the office pantry.
A Python pipeline (a stepdag graph) turns raw scanner events into static JSON; a React app renders it.

- `project.md`: the original brief
- `PRD.md`: requirements and the static JSON contract
- [GitHub issues](https://github.com/snacker-tracker/interface/issues): specs and tickets, labelled by feature


## Layout

| Path | What it is |
|---|---|
| `backend/` | The Python + Polars graph that builds the site's data, managed with uv |
| `stepdag/` | The framework that runs it on Step Functions, one Lambda per asset |
| `frontend/` | Vite + React + TypeScript app |
| `data/` | Raw scanner events and OpenFoodFacts, copied locally (git-ignored) |
| `public-data/` | Generated JSON, written by the graph (git-ignored) |

## Running locally

Requires [uv](https://docs.astral.sh/uv/) and Node 22 (see `frontend/.nvmrc`).

1. Build the data:

   ```sh
   cd backend
   scripts/build-local-data.sh
   ```

   This runs the graph over the raw events in `data/`, and writes `public-data/data/…`. Rerun it
   whenever the raw data changes: it reads only raw files newer than the last run's. The first
   run copies the 8 GB OpenFoodFacts file into `data/files/`. See `backend/README.md`.

2. Run the frontend:

   ```sh
   cd frontend
   npm install
   npm run dev
   ```

   Vite serves `public-data/` as its public directory, so the app loads the built JSON
   from `/data/…`. `npm run build` produces a static site in `frontend/dist/`, with the
   data copied in.

## Checks

```sh
cd backend && uv run pytest && uv run mypy      # backend tests and typecheck
cd frontend && npx tsc -b && npm run lint       # frontend typecheck and lint
```

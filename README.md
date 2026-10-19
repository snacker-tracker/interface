# Snacker Tracker Interface

A read-only web interface showing which snacks are taken from the office pantry.
A Python build step turns raw scanner events into static JSON; a React app renders it.

- `project.md`: the original brief
- `PRD.md`: requirements and the static JSON contract
- `.scratch/snacker-tracker-interface/`: spec and tickets

## Layout

| Path | What it is |
|---|---|
| `backend/` | Python + Polars build CLI (`snacker build`), managed with uv |
| `frontend/` | Vite + React + TypeScript app |
| `data/` | Raw scanner events and OpenFoodFacts, copied locally (git-ignored) |
| `public-data/` | Generated JSON, written by the build (git-ignored) |

## Running locally

Requires [uv](https://docs.astral.sh/uv/) and Node 22 (see `frontend/.nvmrc`).

1. Build the data:

   ```sh
   cd backend
   uv run snacker build --raw ../data/raw/data/scanner --out ../public-data
   ```

   This writes `public-data/data/…`. Rerun it whenever the raw data changes.

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

# snacker (backend)

Build step that turns raw scanner events into the static JSON read by the frontend.
See `PRD.md` at the repo root for the data contract.

```sh
uv run snacker build --raw ../data/raw/data/scanner --out ../public-data
uv run pytest
uv run mypy
```

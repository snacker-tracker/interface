# snacker (backend)

Build step that turns raw scanner events into the static JSON read by the frontend.
See `PRD.md` at the repo root for the data contract.

```sh
uv run snacker extract-products --raw ../data/raw/data/scanner \
  --food ../data/openfoodfacts__product-database/food.parquet --products ../data/products.parquet
uv run snacker build --raw ../data/raw/data/scanner --products ../data/products.parquet --out ../public-data
uv run pytest
uv run mypy
```

Office time zones live in `src/snacker/config.py`: a map from location prefix to IANA
time zone, where the longest prefix wins. A scanned location with no match stops the
build, so add a line there when a scanner goes into a new office.

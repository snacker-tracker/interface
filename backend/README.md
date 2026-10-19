# snacker (backend)

Build step that turns raw scanner events into the static JSON read by the frontend.
See `PRD.md` at the repo root for the data contract. Its shapes are defined in
`src/snacker/contract.py`; after changing them, rerun `snacker schema` to update the
committed JSON Schema (a test fails until you do).

```sh
uv run snacker extract-products --raw ../data/raw/data/scanner \
  --food ../data/openfoodfacts__product-database/food.parquet --products ../data/products.parquet
uv run snacker build --raw ../data/raw/data/scanner --products ../data/products.parquet --out ../public-data
uv run snacker check --out ../public-data     # build already does this
uv run snacker schema --out ../contract/static-json.schema.json
uv run pytest
uv run mypy
```

Office time zones live in `src/snacker/config.py`: a map from location prefix to IANA
time zone, where the longest prefix wins. A scanned location with no match stops the
build, so add a line there when a scanner goes into a new office.

`build` checks what it wrote against the whole output contract (PRD.md §7) before
publishing it: if any file breaks it, the build lists each violation, exits non-zero and
leaves the previous `data/` in place. The rejected build stays in `<out>/.data-building/`
for inspection. A build that passes replaces `data/` entirely, so files a build no longer
writes disappear.

# /// script
# requires-python = ">=3.10"
# dependencies = ["polars==2.0.0"]
# ///
"""Minimal reproduction: Polars panics in `when/then` on a field of a multi-chunk struct column.

Seen on 2.0.0 (the latest release as of 2026-10-19) and on 1.44.2, so it is not new in 2.0.

Run it with no other setup: `uv run polars_multichunk_struct_when_panic.py`

- **Trigger:** a struct column made of more than one chunk (here from `pl.concat(..., rechunk=False)`;
  `pl.scan_ndjson` over several files produces the same), and
  `pl.when(<condition on a column>).then(pl.col(<struct>).struct.field(...))`.
- **Not needed:** nulls of any kind, or reading from disk.
- **Avoids it:** `.rechunk()` before the select, a literal condition (`pl.when(True)`), or
  using `struct.field(...)` outside `when/then`.

Observed panic:

    thread '...' panicked at crates/polars-core/src/chunked_array/struct_/mod.rs:475:9:
    assertion `left == right` failed
      left: 2
     right: 1
"""

import polars as pl

schema = {"v": pl.Int64(), "s": pl.Struct({"x": pl.String()})}
a = pl.DataFrame({"v": [1], "s": [{"x": "a"}]}, schema=schema)
b = pl.DataFrame({"v": [2], "s": [{"x": "b"}]}, schema=schema)

df = pl.concat([a, b], rechunk=False)
print(f"polars {pl.__version__}; chunks per column: {df.n_chunks('all')}")

# Workaround: the same expression after rechunking works.
print(df.rechunk().select(pl.when(pl.col("v") == 2).then(pl.col("s").struct.field("x"))))

# Panics: PanicException (an assertion in polars-core's struct chunked array).
print(df.select(pl.when(pl.col("v") == 2).then(pl.col("s").struct.field("x"))))

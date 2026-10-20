# 26: Scans carry one scanned product (prefactor)

**What to build:** inside the backend, each scan carries its **scanned product** (GLOSSARY.md) as one value rather than five loose product columns. A new product field in the scan lists then means changing how the scanned product is built, not every summary that passes it along. The published JSON doesn't change. This came from the architecture review on 2026-10-20 (candidate 1, "Scanned product").

**Blocked by:** None (can start immediately).

**Status:** resolved

Decisions from the design session:

- **Shape:** the scanned product is a single struct column, shaped exactly like the scanned product in ticket 27: code, name, name source, brands, known and Nutri-Score.
- **Avoiding the Polars panic:** the panic is in `polars_multichunk_struct_when_panic.py`, at the repo root: `when/then` on a struct field of a column with several chunks.
  - Build the struct last, from plain columns, after the join has filled in unknown products (known false, the code kept).
  - Read struct fields only in filters, sorts and aggregations, never inside `when/then`.
  - Rechunk after any concat.
- **Readers:** the latest scans, top scans, the healthiest and least healthy products, and the scanner statuses select or aggregate that one column. For now they flatten it into today's row fields at the output.
- **Tests:** the scans-table fixture builds the struct in one place.
- **Scope:** product files (the code page's card) aren't touched.

- [x] Scans carry a single scanned-product struct, and no summary lists the product columns itself.
- [x] The scanned product is built after the join from plain columns, with no `when/then` on struct fields, and codes scanned since the last extraction are unknown.
- [x] The published JSON is unchanged: every existing test passes without edits to its expectations, and the real data builds to the same files.
- [x] The scans-table fixture builds the struct in one place.

## Comments

- 2026-10-20: Implemented.
  - **Products:**
    - `with_products` joins the plain product columns, fills in unknown codes, and then builds one `product` struct (`SCANNED_PRODUCT`) with `scanned_product`. The struct is built last from plain columns, so there's no `when/then` on its fields.
    - The office-moments concat now rechunks.
  - **Readers:**
    - The latest scans, top scans and the health lists select or aggregate `product`, and flatten it with `{**product, ...}`.
    - The unknown-only and Nutri-Score filters read struct fields in `filter` and `with_columns` only.
    - The scanner statuses still map it onto LastScan's own field names (`product_name`, no brands). Ticket 27 removes that.
  - **Fixture:** `scans_table` builds the struct in one place. Its keyword arguments are unchanged, so no test changed.
  - **Checked:**
    - 137 tests pass with no edits to their expectations, and mypy is clean.
    - Building the real data with the code before and after, at the same fixed build time, gave identical output: 3,466 files.

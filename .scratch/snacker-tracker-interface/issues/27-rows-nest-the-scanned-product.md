# 27: Rows nest the scanned product

**What to build:** the published rows nest the **scanned product** (GLOSSARY.md) as one object, and every scan list renders it with one component. The scanners page's last scan gains what the other lists show: brands and the OpenFoodFacts links. Adding a product field to the lists then means one change per tier. This came from the architecture review on 2026-10-20 (candidate 1, "Scanned product").

**Blocked by:** 26 (Scans carry one scanned product).

**Status:** resolved

Decisions from the design session. The type shape was agreed in that session:

```
ScannedProduct  { code, name, name_source, brands, known, nutri_score }
ScanRow         { product: ScannedProduct, location, scanned_at, office_time, office_time_zone }
TopScan         { product: ScannedProduct, count, share }
LastScan        { product: ScannedProduct, scanned_at }     # gains brands; product_name → name
health-list row { product: ScannedProduct, count }          # no hidden share
ProductFile     unchanged
```

- **The code:** it lives inside the scanned product, not on the row. Rules that read a row's code read its product's code.
- **The health lists:** their rows stop reusing the top-scan row, so they no longer carry a share the UI hides. Name the row type during implementation.
- **The check:** one set of scanned-product rules runs per row: the name source is set exactly when there's a name, an OpenFoodFacts name and a Nutri-Score only for a known product. The rules that were repeated per list go.
- **The frontend:**
  - `ScannedProduct` takes one `product`.
  - Top scans, the latest scans, the healthiest and least healthy products and the scanners page's last scan all render it.
  - A shared row shows the product and its count, and Top scans adds the share, so the `withShare` flag goes.
- **What changes on screen:** the scanners page's last scan shows brands and the OpenFoodFacts links like every other list.
- **Contract:** still version 3 if version 3 hasn't been deployed. Otherwise it's bumped to 4.
- **Scope:** the code page's product file is a different concept (the full card) and doesn't change.

- [x] The schema has one `ScannedProduct` definition. Scan rows, top scans, last scans and health-list rows nest it, and the generated frontend types follow.
- [x] The check applies the scanned-product rules once per row, wherever the row appears.
- [x] Every scan list renders the scanned product with the one component. The scanners page's own copy and the `withShare` flag are gone.
- [x] The build and contract tests expect the nested shape. Behaviour tests keep their seams.
- [x] The real data builds, the check passes, and a server-side render shows a scanned product in each list.
- [x] The PRD (§7, R3, S2) describes the nested rows.

## Comments

- 2026-10-20: Implemented.
  - **Contract:**
    - `ScannedProduct` is one schema definition. `ScanRow`, `TopScan` and `LastScan` nest it as `product`, and health-list rows are `ScannedProductCount` (`{product, count}`).
    - The last scan gains brands, and `product_name` is now `name`. Still version 3.
  - **Backend:** rows take the scan's `product` struct as it is. The casts and the scanner-status field mapping from ticket 26 are gone.
  - **Check:**
    - `_scanned_product` runs the name-source and Nutri-Score rules once per row, in recent scans, both top-scan lists, the health lists and last scans.
    - Every code mentioned is read from `product.code`, and the health lists now count among the codes mentioned.
  - **Frontend:**
    - `ScannedProduct` takes one `product`.
    - The new `ScannedProductRow` (product and count, plus whatever the list adds) serves Top scans, which adds the share, and the health lists. `TopScanRow` and `withShare` are gone.
    - The scanners page's last scan renders `ScannedProduct` in a product cell.
  - **Tests:**
    - A new build test covers the nested shape in every list.
    - A new check breakage covers a last scan's name without a source.
    - The exact-shape expectations in the build, contract, scan-summary, top-scans and health-list tests moved to the nested form.
  - **Checked:**
    - 139 tests pass, and mypy, tsc, lint and the build are clean.
    - The real data builds and passes the check.
    - A server-side render showed the scanned product in Top scans, the health lists, the latest scans and a last scan. The last scan now shows "Add it to OpenFoodFacts".
    - Not checked in a browser.

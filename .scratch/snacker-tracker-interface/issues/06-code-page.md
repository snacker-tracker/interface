# 06: Code page

**What to build:** Clicking a scan opens `/codes/:code`. The page shows the product's name and brands (or "Unknown product"), a scans-per-day chart, a scans-per-hour-of-day chart (24 bars, local time), and the code's 25 most recent scans with local date, time and location. Charts and lists respect the selected location; product information is global. URL-like codes such as QR-code links work too. See PRD §6.3 and §7.

**Blocked by:** 02a (Prefactor: Scan summary and Locations), 03 (Location hierarchy and selector), 04 (Office local time), 05 (Product names in scan lists).

**Status:** resolved

- [x] Scan summary (02a) gains hourly counts. The code files come from summarising the scans for one code within one location, reusing the same module as the index files.
- [x] The build writes one global product file for every scanned code, with `product` null when there's no match.
- [x] For each code and each location where that code was scanned, the build writes a scans file with daily counts, hourly counts (always exactly 24 entries, local hour) and the 25 most recent rows. It follows the "codes / code / by-location / location" layout.
- [x] Codes and locations are percent-encoded path segments. The frontend encodes them twice when fetching, so URL-like codes resolve to the right file on a static server.
- [x] The `/codes/:code` route (single-encoded) shows the product's name and brands or "Unknown product", the daily chart, the hour-of-day chart and the recent-scans list.
- [x] A missing per-location scans file is shown as zero scans, not as an error.
- [x] Recent-scan rows on the index link to their code page and keep `?location`. The location selector works on the code page.
- [x] End-to-end build tests cover product files with and without matches, per-location scans files only where scanned, the 24-entry hourly counts, and encoded paths for URL-like and short codes.

## Comments

- 2026-10-19: Implemented.
  - **Scan summary:** gains `hourly`, always 24 entries, each scan counted in the hour of its office time.
  - **Build output:** `codes/{code}/product.json` for each scanned code (`product` null when unknown), and `codes/{code}/by-location/{location}.json` only for locations where the code was scanned.
  - **Real data:** 854 product files and 2,600 scans files, 24 MB, built in about 4.6s.
  - **Code page:** `/codes/:code` shows the product (or "Unknown product") and the code, a total for the selected location, the daily chart, a new hourly chart (rendered to PNG from real data in light, dark and 320px) and the latest 25 scans (when and where).
  - **Missing data:** `useJson` gains a `missing` state, and a missing scans file shows as zero scans.
  - **Index rows:** they link to the code page from both the product and the code, keeping `?location`.
  - **Links:** they use `encodeURIComponent`. React Router decodes URL, backslash, `?#% ` and Thai codes back exactly. `generatePath` isn't used, because it leaves `:` unencoded.
  - **Shared chart theme:** the Vega config shared by both charts moved into theme.ts (review candidate 6, now that a second chart exists).
  - **Not verified:** the page hasn't been clicked through in a browser.

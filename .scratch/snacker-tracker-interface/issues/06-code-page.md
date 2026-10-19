# 06: Code page

**What to build:** Clicking a scan opens `/codes/:code`. The page shows the product's name and brands (or "Unknown product"), a scans-per-day chart, a scans-per-hour-of-day chart (24 bars, local time), and the code's 25 most recent scans with local date, time and location. Charts and lists respect the selected location; product information is global. URL-like codes such as QR-code links work too. See PRD §6.3 and §7.

**Blocked by:** 02a (Prefactor: Scan summary and Locations), 03 (Location hierarchy and selector), 04 (Office local time), 05 (Product names in scan lists).

**Status:** ready-for-agent

- [ ] Scan summary (02a) gains hourly counts. The code files come from summarising the scans for one code within one location, reusing the same module as the index files.
- [ ] The build writes one global product file for every scanned code, with `product` null when there's no match.
- [ ] For each code and each location where that code was scanned, the build writes a scans file with daily counts, hourly counts (always exactly 24 entries, local hour) and the 25 most recent rows. It follows the "codes / code / by-location / location" layout.
- [ ] Codes and locations are percent-encoded path segments. The frontend encodes them twice when fetching, so URL-like codes resolve to the right file on a static server.
- [ ] The `/codes/:code` route (single-encoded) shows the product's name and brands or "Unknown product", the daily chart, the hour-of-day chart and the recent-scans list.
- [ ] A missing per-location scans file is shown as zero scans, not as an error.
- [ ] Recent-scan rows on the index link to their code page and keep `?location`. The location selector works on the code page.
- [ ] End-to-end build tests cover product files with and without matches, per-location scans files only where scanned, the 24-entry hourly counts, and encoded paths for URL-like and short codes.

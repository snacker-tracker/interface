# 03: Location hierarchy and selector

**What to build:** Office management picks a location from a prominent selector in the header (`all`, `thailand`, `thailand:bangkok`, `thailand:bangkok:main-kitchen`, …), and the index page shows only scans within that location and everything beneath it. Bangkok's old (`thailand:bangkok`) and new (`thailand:bangkok:main-kitchen`) scans both appear under `thailand:bangkok`. The selection lives in the browser URL so links can be shared. See PRD R2, G1 and G2.

**Blocked by:** 02 (Index page), 02a (Prefactor: Scan summary and Locations).

**Status:** resolved

- [x] The build writes a locations file listing `all` plus every prefix of every observed location.
- [x] The build writes one index file per selectable location, under the "index / by-location / location" layout, with path segments percent-encoded.
- [x] The hierarchy rules live in the Locations module (02a): its selectable set grows to every prefix, and `within` matches whole segments. Tests for these rules sit at the Locations seam; build tests check one file per location.
- [x] A location includes its descendants, matched on whole segments only: a partial segment such as `thailand:bang` matches nothing.
- [x] Test locations such as `thailand:test` are kept like any other location.
- [x] The header shows a location selector on every page, populated from the locations file.
- [x] The selection is stored as `?location=` in the browser URL and defaults to `all` when absent. Changing it keeps the user on the current page, and reloading or sharing the URL keeps the filter.
- [x] The index page fetches the index file for the selected location.
- [x] End-to-end build tests cover prefix inclusion, whole-segment matching, the set of selectable locations, test-location retention, and one file per location.

## Comments

- 2026-10-19: Implemented.
  - **Hierarchy:** it lives in Locations. `selectable()` returns `all` plus every prefix in path order, and `within()` matches whole segments. Its tests sit at the Locations seam, per the 02a decision: prefixes, whole segments (`thailand:bangkok-annex` is excluded), test-location retention, and refusing `thailand:bang`.
  - **Build output:** the build writes `locations.json` and one index file per location. Build tests check the file set and the encoding.
  - **Encoding (decided with the user):** file names are encoded like `encodeURIComponent` but keep `:` literal. The frontend applies the same encoding twice when fetching. Vite doesn't match `%3A`, so `:` stays literal in requests. PRD §7.3 is updated. The Python and JS encoders agree on 7 tricky values.
  - **Real data:** the dev and preview servers serve every location: all 8,084, thailand 8,084, thailand:bangkok 8,083, main-kitchen 68, thailand:test 1.
  - **Frontend:** the header selector reads and writes `?location=`, and `all` is left out of the URL. The title link keeps the filter, and labels are indented by depth with non-breaking spaces.
  - **Not verified:** the selector hasn't been clicked through, because there's no browser on the dev machine.

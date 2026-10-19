# 03: Location hierarchy and selector

**What to build:** Office management picks a location from a prominent selector in the header (`all`, `thailand`, `thailand:bangkok`, `thailand:bangkok:main-kitchen`, …), and the index page shows only scans within that location and everything beneath it. Bangkok's old (`thailand:bangkok`) and new (`thailand:bangkok:main-kitchen`) scans both appear under `thailand:bangkok`. The selection lives in the browser URL so links can be shared. See PRD R2, G1 and G2.

**Blocked by:** 02 (Index page).

**Status:** ready-for-agent

- [ ] The build writes a locations file listing `all` plus every prefix of every observed location.
- [ ] The build writes one index file per selectable location, under the "index / by-location / location" layout, with path segments percent-encoded.
- [ ] A location includes its descendants, matched on whole segments only: a partial segment such as `thailand:bang` matches nothing.
- [ ] Test locations such as `thailand:test` are kept like any other location.
- [ ] The header shows a location selector on every page, populated from the locations file.
- [ ] The selection is stored as `?location=` in the browser URL and defaults to `all` when absent. Changing it keeps the user on the current page, and reloading or sharing the URL keeps the filter.
- [ ] The index page fetches the index file for the selected location.
- [ ] End-to-end build tests cover prefix inclusion, whole-segment matching, the set of selectable locations, test-location retention, and one file per location.

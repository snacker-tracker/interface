Status: ready-for-agent

# Spec: Snacker Tracker Interface

Detailed source analysis, data contract and rationale are in the PRD at the repo root.

## Problem Statement

Office management wants to know which snacks people take from the pantry so the next grocery list matches real preferences. Office-goers are curious about what's being taken.

An internet-connected barcode scanner in the Bangkok office already publishes scan events and heartbeats, and they land in S3. Years of older scans have been backfilled from a previous system. None of this can be seen anywhere today. The data is raw JSON event envelopes in two different historical formats, product names aren't attached, and nobody can tell whether the scanner is even working.

More offices are expected to get scanners soon, so whatever is built must not assume a single office or a single time zone.

## Solution

A read-only web interface backed entirely by pre-generated static JSON.

A Python + Polars build step:
- reads the raw scan and heartbeat events
- joins scans with product information pulled from OpenFoodFacts
- writes one set of JSON files for each location in the location hierarchy

A React frontend renders those files with Vega-Lite charts. It has two pages:
- **Index:** scans per day across all history, plus the 25 most recent scans.
- **Code page:** one product's information, scans per day, scans per hour of day, and its 25 most recent scans.

Every page has a prominent location selector, with `all` as an option, and a scanner status widget that shows whether each scanner in the selected location has sent a heartbeat in the last hour.

## User Stories

1. As office management, I want a bar chart of scans per day, so that I can see how pantry consumption changes over time.
2. As office management, I want the daily chart to cover all recorded history, so that I can compare current consumption with earlier years.
3. As office management, I want to brush-select a date range on the daily chart to zoom in, so that I can inspect a specific period without losing the overview.
4. As an office-goer, I want to see the 25 most recent scans on the welcome page, so that I can see what was just taken.
5. As an office-goer, I want each recent scan to show the product name and brand, so that I recognise the snack without looking up a barcode.
6. As an office-goer, I want each recent scan to show when and where it was scanned, so that I know how recent it is and which pantry it came from.
7. As an office-goer, I want to click a recent scan to open that product's page, so that I can learn more about it.
8. As office management, I want a page for each scanned code, so that I can study demand for one product.
9. As office management, I want the code page to show the product's name, brands, quantity, image and categories, so that I know exactly which item and pack size it is when buying.
10. As office management, I want a link from the code page to the product on OpenFoodFacts, so that I can see fuller details there.
11. As office management, I want a scans-per-day chart on the code page, so that I can see whether a product is gaining or losing popularity.
12. As office management, I want a scans-per-hour-of-day chart on the code page, so that I know when a product is most in demand, for example morning coffee or afternoon snacks.
13. As office management, I want the hour-of-day chart to always show all 24 hours, so that quiet hours are visible as zero rather than missing.
14. As an office-goer, I want the code page to list the product's 25 most recent scans with date, time and location, so that I can see who else likes it and where.
15. As office management, I want a location selector on every page, so that I can focus on one office or pantry.
16. As office management, I want an `all` option in the location selector, so that I can see consumption across every office.
17. As office management, I want to select a city or country and include every pantry within it, so that I can compare at the level I care about.
18. As office management, I want Bangkok's old and new scans to both appear when I select Bangkok, so that switching scanner systems doesn't split the history.
19. As office management, I want the selected location in the browser URL, so that a link I share shows the same filter to colleagues.
20. As an office-goer, I want to keep my selected location when I move from the index to a code page, so that I don't have to reselect it.
21. As office management, I want the code page's charts and recent scans filtered by the selected location, so that product demand reflects the office I'm planning for.
22. As office management, I want product information to stay the same regardless of location, so that the product is always identified correctly.
23. As office management, I want days and hours counted in the office's local time, so that a 9am snack shows at 9am and not at 2am UTC.
24. As office management in a future office, I want my office's scans bucketed in my office's own time zone, so that charts are correct for every office.
25. As office management viewing `all` across time zones, I want each scan counted in its own office's local day and hour, so that a combined view is meaningful.
26. As an office-goer, I want scan times shown in the office's local time with the time zone indicated, so that times aren't ambiguous.
27. As an office-goer, I want scans of codes with no product information shown as "Unknown product" with the raw code, so that every scan is visible even when unidentified.
28. As office management, I want scans of QR codes and odd short codes counted in every chart and list, so that totals reflect everything that was taken.
29. As an office-goer, I want URL-like codes to have working code pages, so that every entry in a list is clickable.
30. As office management, I want the product name to use OpenFoodFacts' main name, so that it matches what's printed on the pack.
31. As a maintainer, I want a scanner status widget on every page, so that I notice immediately if a scanner stops working.
32. As a maintainer, I want the widget to list each scanner in the selected location with its name, so that I know which device I'm looking at.
33. As a maintainer, I want to see how long ago each scanner last sent a heartbeat, so that I can judge whether it's alive.
34. As a maintainer, I want a scanner flagged as offline after more than one hour without a heartbeat, so that outages stand out without false alarms.
35. As a maintainer, I want to see each scanner's app version, so that I know whether a firmware update has been rolled out.
36. As a maintainer, I want the widget to show when the data was last built, so that I can tell a dead scanner apart from stale data.
37. As a maintainer, I want heartbeats in every historical payload shape understood, so that status works across firmware versions.
38. As a maintainer, I want the build to fail if a location has no configured time zone, so that a new office never silently gets wrong charts.
39. As a maintainer, I want test locations kept like any other location, so that I can check a new scanner end to end through the real UI.
40. As a maintainer, I want duplicate events counted once, so that redelivered events don't inflate the counts.
41. As a maintainer, I want the build to read scans in both the backfill format and the live format, so that all history is included.
42. As a maintainer, I want scans without a device timestamp to fall back to the time the event was received, so that live scans are still placed in time.
43. As a maintainer, I want product extraction from the large OpenFoodFacts file to be a separate step that only reruns when new codes appear or I force it, so that routine builds are fast.
44. As a maintainer, I want the output to be plain static files at predictable paths with no query parameters, so that it can be hosted on any static host or S3.
45. As a data engineer, I want each backend step to be a clearly named function with explicit inputs and outputs, so that I can lift it into a Dagster asset with little rework.
46. As a data engineer, I want the time zone map and the recent-list size in configuration, so that onboarding an office or changing N needs no code change.
47. As a developer, I want the frontend to show zero scans when a location has no data for a code, so that missing combinations don't break the page.
48. As a developer, I want every scanned code to have a product file even when there's no match, so that the frontend never has to treat "no product" as a failed request.
49. As a developer, I want scan rows to carry product name and brands already, so that a list renders from a single request.

## Implementation Decisions

### Overall shape

The backend is a build pipeline, not a server. It is a uv-managed Python package using Polars and exposed as a CLI. There is no Python process at request time; any static file server serves the output, with Vite doing this in development.

The repo is a monorepo with a backend project, a frontend project and a generated output folder. The raw data folder and the generated output folder are git-ignored.

### Backend modules

Each module is a pure step with explicit inputs and outputs, so each maps onto one Dagster asset.

- **Product extraction**
  - Input: the OpenFoodFacts food parquet and the set of scanned codes.
  - Output: a small products table with code, main name, brands, quantity, categories, image source and OpenFoodFacts URL.
  - Only scanned codes and needed columns are kept.
  - It reruns only when there are codes it hasn't seen yet, or when forced.
  - OpenFoodFacts has no `brand` column; `brands` is used.
  - The name comes from the `main` entry of the multilingual `product_name` list, falling back to the first entry.
  - Building the image URL from the `images` column is to be resolved during implementation.
- **Scan normalisation**
  - Input: raw scan files, which may hold one or more JSON envelopes each, one per line.
  - Output: a single table with event ID, code (always a string), location, `scanned_at` in UTC, `scanned_at_source` (`device` or `reported`) and `origin` (`backfill` or `live`, for debugging only).
  - `scanned_at` comes from the payload when present, otherwise from the envelope `time`.
  - Both eras are handled: `/scans` from `from-backup`, and `scans` from `scanner`.
  - Duplicate event IDs are dropped.
- **Heartbeat normalisation**
  - Input: raw heartbeat files in any of three payload shapes:
    - unversioned flat
    - unversioned flat with telemetry
    - `schema_version` 2, nested under `device` and `app`
  - Output: device name, location, app version and last-seen time for each scanner.
- **Location hierarchy**
  - Locations are colon-separated paths, and a location includes all of its descendants.
  - Matching is on whole segments only.
  - The selectable set is `all` plus every prefix of every observed location.
  - `thailand:test` and similar locations are kept.
- **Time zone resolution**
  - A config map from location prefix to IANA time zone, where the longest prefix wins.
  - An unmapped location is a build error.
  - Bucketing converts each scan to its own office's local time, so `all` and multi-time-zone parents are still correct.
- **Build / publish**
  - Input: the normalised scans, the scanner status, the products table, config, and an injected "generated at" time.
  - Output: the static JSON tree.

### Static JSON contract

The contract is part of the interface between backend and frontend. Shapes are indicative; exact field names are settled in implementation and pinned by the output contract tests.

- A meta file holding the build time.
- A locations file listing every selectable location, including `all`.
- **For each location, an index file** containing:
  - daily counts as `{date, count}` in local dates, with zero days left out
  - the recent 25 scan rows, newest first
- **For each location, a scanners file** listing each scanner within it: device name, location, app version, last seen.
- **For each code, one global product file**, whose product is `null` when there's no match.
- **For each code and location where that code was scanned, a scans file** containing:
  - daily counts
  - hourly counts, always exactly 24 entries
  - the recent 25 rows
- **Every scan row** carries code, product name or null, brands or null, location, UTC timestamp, local time and time zone.
- **Layout:** the "thing / by-location / location" pattern, with codes grouped first: a code's product file and its per-location scan files live together under that code.
- **Encoding:**
  - Codes and locations are path segments, percent-encoded like `encodeURIComponent`.
  - Barcodes and `thailand:bangkok` stay readable.
  - URL codes are encoded but can be decoded back.
  - Static servers decode escapes before looking up a file, so the frontend encodes segments twice when fetching. Browser routes use single encoding.

### Frontend

- Vite, React, TypeScript, React Router, `react-vega` and Node 22 LTS.
- **Routes:** the index at the root and the code page at `codes/:code`, exactly as specified.
- **Location:** an optional `location` query parameter in the browser URL, defaulting to `all`. Query parameters are used only in the browser URL, never in data file paths. Changing the selection keeps the current page, and links between pages keep the parameter.
- **Header:** the location selector and the scanner status widget appear on every page.
- **Offline status:** worked out in the browser as more than one hour between now and last seen.
- **Missing data:** a missing per-location scans file means zero scans.
- **Unknown products:** shown as "Unknown product" plus the raw code.
- **Index chart:** all-history daily bars with brush-to-zoom.
- **Hour-of-day chart:** 24 bars in local time.

## Testing Decisions

### What a good test is

A good test checks behaviour through a public seam using realistic inputs, and asserts on observable outputs. It should not reach into intermediate DataFrames, helper functions or column names. Internal steps can be reorganised freely without breaking tests.

Tests use small fixture files written in the real envelope formats. They never use the real raw data or the 8 GB OpenFoodFacts file.

### Seams

Two seams are needed, agreed with the user.

**Seam 1: the build, end to end (primary)**
- Input: fixture raw scan and heartbeat files, a fixture products table, config, and a fixed "generated at" time.
- Action: run the build into a temporary output folder.
- Assertions: on the set of file paths written and on the JSON contents.

Behaviours to cover:
- **Parsing both scan eras:** backfill with a device timestamp, and live falling back to the envelope time.
- **Multi-event files:** files with several events, and duplicate event IDs counted once.
- **Location hierarchy:** prefix inclusion, whole-segment matching (a partial segment matches nothing), `all`, and the selectable set including every prefix.
- **Test locations:** `thailand:test` kept.
- **Local-time buckets:** scans just either side of UTC midnight and local midnight land on the correct local date and hour, and multi-time-zone `all` buckets each scan in its own zone.
- **Hourly counts:** always exactly 24 entries.
- **Recent lists:** the last 25, newest first, carrying product name and brands, or nulls.
- **Product files:** written for every scanned code, with `product` null when there's no match.
- **Per-location scan files:** written only where the code was scanned.
- **Encoding:** URL-like and short codes get correctly encoded file paths.
- **Unmapped time zone:** a location with no configured time zone fails the build with a clear error.
- **Heartbeats:** all three shapes produce scanner entries with the right name, location, version and latest last-seen time, grouped correctly under each location level.
- **Build time:** the meta file reflects the injected build time.

**Seam 2: product extraction**
- Input: a tiny fixture parquet with the real OpenFoodFacts column types (multilingual name list, brands, quantity, categories, images) and a set of codes.
- Assertions: on the resulting products table.

Behaviours to cover:
- Only the requested codes are kept, and unmatched codes are left out.
- The `main` name is picked, falling back when `main` is missing.
- Brands, quantity and categories are carried through.

### Out of test scope this phase

The frontend has no automated tests.

### Prior art

None. The codebase is empty, and these tests establish the pattern. Use pytest.

## Out of Scope

- Authentication, user accounts, or attributing scans to individuals.
- Any write path from the UI.
- Heartbeat telemetry beyond last seen and version: wifi RSSI, uptime, free memory, reset cause.
- Nutrition data.
- Range toggles or weekly/monthly roll-ups on the index chart.
- A dedicated scanner health page.
- Frontend automated tests.
- Running in Dagster or reading directly from S3. The code is shaped for that move but doesn't make it.
- Deployment and hosting.

## Further Notes

- **Data profile (2026-10-19)**
  - 8,084 scans and 854 distinct codes.
  - 8,016 of the scans are 2019–2023 backfill and 68 are live from 2026-09 onward, leaving a gap of about 3 years.
  - About 204 scans are non-barcode codes.
  - 508 codes, about 80% of scans, match OpenFoodFacts.
  - There are about 11k heartbeats from a single device.
- **Firmware anomaly:** one schema-2 heartbeat reports a negative uptime. It doesn't affect this work but is worth raising with firmware.
- **Locations:** backfill scans use `thailand:bangkok` and live scans use `thailand:bangkok:main-kitchen`. The hierarchy rule is what joins Bangkok's history together.
- **Code clarity:** the backend is expected to be rewritten or absorbed into Dagster, so clarity of each step matters more than cleverness.

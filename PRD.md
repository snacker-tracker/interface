# PRD: Snacker Tracker Interface

Status: agreed, ready to build · Last updated: 2026-10-19
Builds on: [project.md](project.md)

## 1. Summary

A read-only web interface showing which snacks are being taken from the office pantry. The aim is to inform the next grocery list and give office-goers visibility.

A Python + Polars **build step** turns raw scanner events and OpenFoodFacts data into **static JSON files**. A React frontend renders those files. No server runs at request time.

## 2. Goals and non-goals

### Goals

- Show scan volume over time and the most recent scans, filterable by location.
- Show per-product detail: product info, scans over time, scans by hour of day, recent scans.
- Show whether each scanner is alive (last heartbeat, app version).
- Support more offices than Bangkok without code changes beyond configuration.
- Keep the backend easy to lift into a Dagster pipeline later.

### Non-goals (for now)

- Authentication, user accounts, or attributing scans to people.
- Writing or editing data from the UI.
- Scanner telemetry beyond last-seen and version (RSSI, memory, uptime, reset cause).
- Nutrition data (Nutri-Score, NOVA, nutrients).
- Frontend automated tests.

## 3. Users

- **Office management**: reads trends and popular products to plan purchasing.
- **Office-goers**: browse what's being taken.
- **Maintainer**: checks scanners are online.

## 4. Source data

All raw data is JSON wrapped in an AWS EventBridge envelope. A file can hold one or more events, one per line. In production the data lives on S3. For development it has been copied to `data/raw/data/scanner/`.

### 4.1 Scans (`scanner/scans/YYYY/MM/DD/*`)

Profiled 2026-10-19: 8,084 events, 854 distinct codes.

| | Backfill | Live |
|---|---|---|
| Period | 2019-10 → 2023-07 | 2026-09 → present |
| Count | 8,016 | 68 |
| `source` | `from-backup` | `scanner` |
| `detail-type` | `/scans` | `scans` |
| Location seen | `thailand:bangkok` | `thailand:bangkok:main-kitchen` |
| `payload.scanned_at` | present | absent |
| `apiKeyId` | null | set |

There is also one scan at `thailand:test`. About 204 scans (130 codes) are not product barcodes: they are QR-code URLs (up to 88 characters) or short codes such as `005`.

### 4.2 Heartbeats (`scanner/heartbeats/YYYY/MM/DD/*`)

About 11k events since 2026-09-04, sent every few minutes, all from one device (`rpi-pico-w-01`, `thailand:bangkok:main-kitchen`). The payload comes in three shapes:

| Shape | Name | Location | App version |
|---|---|---|---|
| Unversioned, flat | `device_name` | `location` | `version` |
| Unversioned, flat with telemetry | `device_name` | `location` | `version` |
| `schema_version: 2` | `device.name` | `device.location` | `app.version` |

Known anomaly: one v2 event reports a negative `telemetry.uptime`, which looks like a firmware bug. It doesn't affect this product.

### 4.3 OpenFoodFacts (`data/openfoodfacts__product-database/food.parquet`)

- The file is 8 GB, with 111 columns.
- 508 of the 854 codes match, which covers about 80% of scans.
- There is no `brand` column. Use `brands`.
- `product_name` is a list of `{lang, text}` entries.

## 5. Domain rules

### R1: One scan model

Both eras are normalised into one table, which the UI treats identically:

| Column | Notes |
|---|---|
| `event_id` | Envelope `id` |
| `code` | Always a string |
| `location` | |
| `scanned_at` | UTC. `payload.scanned_at` if present, otherwise the envelope `time` |
| `scanned_at_source` | `device` or `reported` |
| `origin` | `backfill` or `live`; for debugging only |

Duplicate `event_id`s are dropped.

### R2: Locations are hierarchical

- A location is a colon-separated path such as `thailand:bangkok:main-kitchen`.
- Selecting a location includes all locations beneath it, matched on whole segments: `thailand:bang` matches nothing.
- The selectable set is `all` plus every prefix of every observed location: `thailand`, `thailand:bangkok`, `thailand:bangkok:main-kitchen`, and so on.
- `thailand:test` is kept and treated like any other location.

### R3: All codes count

Every scan counts in every chart and list, whether or not the code is a barcode or has product info. Codes without product info display as **"Unknown product"** with the raw code.

### R4: Office time

- Timestamps are stored in UTC.
- Day and hour buckets use the office time zone of the location the scan came from (see GLOSSARY.md).
- Displayed times are shown in the scan's office time, with the time zone indicated.
- Time zones come from a **prefix map** in backend config, e.g. `{"thailand": "Asia/Bangkok"}`. The longest matching prefix wins. An unmapped location **fails the build**.
- `all`, and parent locations spanning several time zones, bucket each scan in its own office time zone.

### R5: Product display

- **Name:** the `main` entry of `product_name`, falling back to the first available entry.
- **Shown fields:** name, `brands`, `quantity`, image, categories (as tags), and a link to the product's OpenFoodFacts page.

### R6: Scanner status

- Heartbeats from all three shapes are normalised to `{device_name, location, app_version, last_seen}`.
- A scanner is **offline** if `now − last_seen > 1 hour`, evaluated in the browser.
- Because data is pre-built, the UI also shows when the data was generated, so stale data is visible.

## 6. Functional requirements

### 6.1 Global

- **G1:** A prominent **location selector** appears in the header on every page. It lists `all` plus every hierarchy level from R2.
- **G2:** The selected location is held in the browser URL as `?location=<location>`. If absent, it defaults to `all`. Changing the selection keeps the user on the current page.
- **G3:** The header links to a **scanners page** (`/scanners`). The link reads "✕ N offline" when any scanner within the selected location is offline (R6). The page lists each scanner within the selected location: status, name, location, last heartbeat, last scan (tied to the scanner by API key, docs/adr/0002) and app version. It also shows the data build time. (Changed from a header widget by ticket 10.)

### 6.2 Index page: `/`

- **I1:** Bar chart of scans per local day across **all history**, with brush-to-zoom.
- **I2:** List of the **last 25 scans**: local date and time, location, product name and brands (or "Unknown product" and the code). Each row links to its code page, keeping `?location`.

### 6.3 Code page: `/codes/:code`

- **C1:** Product info per R5, or "Unknown product" and the raw code if there's no match.
- **C2:** Bar chart of scans per local day for this code.
- **C3:** Bar chart of scans per local hour of day (0–23), always 24 bars.
- **C4:** List of the last 25 scans of this code: local date and time, location.
- **C5:** C2–C4 are filtered by the selected location. C1 is global.
- **C6:** `:code` is the URL-encoded code (see §7.3).

## 7. Data contract (static JSON)

The build writes everything under `public-data/data/`. No file needs query parameters to be served.

### 7.1 Files

```
data/meta.json                                  { generated_at }
data/locations.json                             all selectable locations
data/index/by-location/{location}.json          index page data
data/scanners/by-location/{location}.json       status widget data
data/codes/{code}/product.json                  product info (global)
data/codes/{code}/by-location/{location}.json   code page scan data
```

- One file is written per `{location}` for every entry in `locations.json`, including `all`.
- `codes/{code}/by-location/{location}.json` is only written for locations where that code was scanned. If the file is missing, the frontend shows zero scans.
- `product.json` is written for **every** scanned code, with `"product": null` when there is no OpenFoodFacts match.

### 7.2 Shapes (indicative)

```jsonc
// locations.json
{ "locations": [ { "id": "all" }, { "id": "thailand" }, { "id": "thailand:bangkok" }, ... ] }

// index/by-location/{location}.json
{
  "location": "thailand:bangkok",
  "daily": [ { "date": "2026-10-16", "count": 4 } ],         // local dates; zero days omitted
  "recent": [ ScanRow ]                                      // newest first, max 25
}

// codes/{code}/by-location/{location}.json
{
  "code": "8850999220000",
  "location": "all",
  "daily": [ { "date": "...", "count": 3 } ],
  "hourly": [ { "hour": 0, "count": 0 }, ... ],              // exactly 24 entries
  "recent": [ ScanRow ]
}

// codes/{code}/product.json
{ "code": "...", "product": null | { "name", "brands", "quantity", "image_url", "categories": [], "off_url" } }

// scanners/by-location/{location}.json
{ "location": "...", "scanners": [ { "name", "location", "app_version", "last_seen" } ] }

// ScanRow
{ "code", "name": null | "...", "brands": null | "...", "location", "scanned_at", "office_time", "office_time_zone" }
```

### 7.3 Encoding

- `{code}` and `{location}` are file names percent-encoded like `encodeURIComponent`, **except that `:` stays literal**. So barcodes and `thailand:bangkok` stay readable, while a URL code becomes `http:%2F%2Fwww.example.com%2F…`. (Decided 2026-10-19. The cost is that `:` isn't a valid file-name character on Windows.)
- Static servers decode `%` escapes before looking up a file, so the frontend **applies the same encoding again** when fetching, still leaving `:` literal. For example, `thailand:staff room` is stored as `thailand:staff%20room.json` and requested as `thailand:staff%2520room.json`. Vite's dev server doesn't match `%3A` to a literal `:`, which is why `:` stays literal in requests too.
- Browser routes use single encoding.

## 8. Technical design

### 8.1 Backend (`backend/`, Python, Polars, uv)

The backend is a CLI with no running server. Each step is a pure function with explicit inputs and outputs, so it maps 1:1 onto a Dagster asset later.

| Step | Input | Output |
|---|---|---|
| `extract-products` | `food.parquet`, scanned codes | `products.parquet` (scanned codes and needed columns only) |
| `normalise-scans` | raw scan files | scans table (R1) |
| `normalise-heartbeats` | raw heartbeat files | scanner status table (R6) |
| `build` | the three tables above + time zone config | JSON files (§7) |

- `extract-products` reruns only when there are unseen codes or a `--force` flag. This keeps normal builds off the 8 GB file.
- Configuration covers the time zone prefix map, the recent-list size N (25), and the input and output paths.

### 8.2 Frontend (`frontend/`)

- Vite, React, TypeScript, React Router (`/`, `/codes/:code`).
- Charts use Vega-Lite via `react-vega`.
- Node 22 LTS, pinned in `.nvmrc`.
- In development, Vite serves `public-data/` as static files.

### 8.3 Repository

- A monorepo initialised with `git init`, containing `backend/`, `frontend/`, `PRD.md` and `project.md`.
- `data/` and `public-data/` are git-ignored.

## 9. Testing

Backend tests run against small fixture files, never the real data:

- **Parsing and normalising**
  - Both scan eras.
  - The `scanned_at` fallback.
  - All three heartbeat shapes.
  - Duplicate event IDs.
- **Aggregations**
  - Location prefix matching on whole segments.
  - Local-time day and hour bucketing, including scans near UTC and local midnight.
  - An unmapped location failing the build.
  - Last-N ordering.
  - Product name selection, including no match.
- **Output contract**
  - A fixture build writes the expected paths, including URL-encoded codes and locations.
  - The JSON matches the expected shapes, including `product: null` and 24-entry `hourly`.

Frontend tests are out of scope for this phase.

## 10. Future / open

- Choose an image URL source from the OpenFoodFacts `images` column (resolve during implementation).
- Range toggle or weekly/monthly roll-ups on the index chart, if the all-history daily chart proves hard to read.
- A scanner health page with telemetry.
- Nutrition info on code pages.
- Frontend component tests.
- Moving the build into Dagster, reading from S3.

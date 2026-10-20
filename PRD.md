# PRD: Snacker Tracker Interface

Status: built (tickets 01–10) · Last updated: 2026-10-19 to match the code
Builds on: [project.md](project.md)

## 1. Summary

A read-only web interface showing which snacks are being taken from the office pantry. The aim is to inform the next grocery list and give office-goers visibility.

A Python + Polars **build step** turns raw scanner events and OpenFoodFacts data into **static JSON files**. A React frontend renders those files. No server runs at request time.

## 2. Goals and non-goals

### Goals

- Show scan volume over time, the most recent scans and the top scans per period, filterable by location.
- Show per-product detail: product info, scans over time, scans by hour of day, recent scans.
- Show whether each scanner is alive (last heartbeat, last scan, app version).
- Support more offices than Bangkok without code changes beyond configuration.
- Keep the backend easy to lift into a Dagster pipeline later.

### Non-goals (for now)

- Authentication, user accounts, or attributing scans to people.
- Writing or editing data from the UI.
- Scanner telemetry beyond last-seen and version (RSSI, memory, uptime, reset cause).
- Nutrients and other nutrition data beyond the grades (R5).
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

About 11k events since 2026-09-04, sent every few minutes, all from one scanner (`rpi-pico-w-01`, `thailand:bangkok:main-kitchen`). The payload comes in three shapes:

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

### 4.4 Snacker archive (`data/codes.csv`)

- The previous Snacker Tracker's product records (GLOSSARY.md), pulled from shop websites or entered by hand. Frozen: nothing is added or corrected.
- 494 rows with `code,name,created_at,updated_at,url,categories`. Only `name` is used; it is trimmed.
- Codes match scanned codes exactly, odd ones like `8 858985 300118` and `ub` included.
- Codes `5` and `78` are recorded twice with different products. A code recorded more than once gets no archive name.
- Some names are wrong for their barcode (8886467100017 is "Pringles original" on OpenFoodFacts but ladies' hot pants in the archive), so an OpenFoodFacts name always wins.
- On the current data it names 97 unknown products and 10 known products OpenFoodFacts has no name for.

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
| `api_key` | The scanner's API key (envelope `apiKeyId`); null for backfill. Ties scans to scanners (R6) |

Duplicate `event_id`s are dropped.

### R2: Locations are hierarchical

- A location is a colon-separated path such as `thailand:bangkok:main-kitchen`.
- Selecting a location includes all locations beneath it, matched on whole segments: `thailand:bang` matches nothing.
- The selectable set is `all` plus every prefix of every observed location: `thailand`, `thailand:bangkok`, `thailand:bangkok:main-kitchen`, and so on.
- `thailand:test` is kept and treated like any other location.

### R3: All codes count

Every scan counts in every chart and list, whether or not the code is a barcode or has product info.

- A code OpenFoodFacts doesn't have is an **unknown product** (GLOSSARY.md), even when the Snacker archive names it.
- A product's name comes from OpenFoodFacts when it has one, otherwise from the Snacker archive (§4.4). An archive name is always tagged "Snacker archive"; OpenFoodFacts names aren't tagged.
- In the scan lists (Top scans, the latest scans and a scanner's last scan), a product with a name shows its name and brands, with its code only as the name's tooltip. An unknown product with an archive name also links to "Add it to OpenFoodFacts". A product without a name shows its raw code instead, with a link to OpenFoodFacts if the code is a barcode: "Add it to OpenFoodFacts" (`https://world.openfoodfacts.org/cgi/product.pl?type=search_or_add&action=process&code={code}`) for an unknown product, "On OpenFoodFacts" (`https://world.openfoodfacts.org/product/{code}`) for a known one without a name.
- In the same lists, a product with a Nutri-Score shows it last, as a compact form of the code page's badge with the same tooltip (R5), whether or not it has a name. The NOVA group and Green-Score are shown only on the code page.
- The code page shows "Unknown product" and the raw code for a product without a name.

### R4: Office time

- Timestamps are stored in UTC.
- Day and hour buckets use the office time zone of the location the scan came from (see GLOSSARY.md).
- Displayed times are shown in the scan's office time, with the time zone indicated.
- Time zones come from a **prefix map** in backend config, e.g. `{"thailand": "Asia/Bangkok"}`. The longest matching prefix wins. An unmapped location **fails the build**.
- `all`, and parent locations spanning several time zones, bucket each scan in its own office time zone.

### R5: Product display

- **Name:** the `main` entry of `product_name`, falling back to the first available entry. Without one, the Snacker archive's name, tagged "Snacker archive" (R3).
- **Shown fields:** name, `brands`, `quantity`, grades, image, categories (as tags), and a link to the product's OpenFoodFacts page.
- **Grades** (GLOSSARY.md): the Nutri-Score (A–E), NOVA group (1–4) and Green-Score (A+–F) from OpenFoodFacts's `nutriscore_grade`, `nova_group` and `environmental_score_grade`. Each is a text badge on its grade's colour, e.g. "Nutri-Score B", with a tooltip saying what the grade means. A grade OpenFoodFacts lacks, or gives as "unknown" or "not-applicable", is left out. Raw scores aren't shown.
- **Archive only:** a product only the Snacker archive has shows its tagged name and the code, then "Not on OpenFoodFacts" and "Add it to OpenFoodFacts" for a barcode. It has no image, brands, quantity, grades or categories.

### R6: Scanner status

- Heartbeats from all three shapes are normalised to one row each: scanner name, location, app version, sent time and API key.
- A scanner is known once it has sent a heartbeat. Its status comes from its latest heartbeat: `{name, location, app_version, last_seen}`.
- A scanner's **last scan** is the latest scan sent with the API key of its latest heartbeat (docs/adr/0002). Backfill scans have no key and never count, and each scanner must have its own key.
- A scanner is **offline** if `now − last_seen > 1 hour`, evaluated in the browser. Scans don't count.
- Because data is pre-built, the UI also shows when the data was generated, so stale data is visible.

### R7: Top scans

- **Top scans** rank codes by number of scans within a **period**, most first (GLOSSARY.md). Unknown products are included.
- The periods, in order: `today`, `this-work-week`, `last-7-days`, `this-month`, `last-30-days`, `this-year`, `last-365-days`, `all-time`.
- Every period ends at the build time. Scans after the build time fall in no period.
- Calendar periods (today, this work week from Monday 00:00 with weekends included, this month, this year) start at midnight in each scan's own office time zone.
- Rolling periods are exact durations back from the build time, and a scan exactly at the cutoff counts.
- Each list holds at most N codes (N = 10, in config), with ties going to the most recently scanned. Each row has the code, name and where the name came from, brands, whether the product is known, its Nutri-Score, the count, and its share of the period's scans.
- A second set of lists ranks **unknown products only** (ticket 11): every unknown code is ranked, not just those in the overall top N, and shares are still of all scans in the period. Unnamed products OpenFoodFacts has aren't included.

### R8: Healthiest and least healthy products

- For every period of R7, the **healthiest and least healthy products** (GLOSSARY.md): the products with a Nutri-Score scanned within it. A product without a Nutri-Score is left out.
- **Ranking:** they are ranked by Nutri-Score grade, then by scans in the period, with ties going to the most recently scanned. The healthiest are best grade first, and the least healthy are worst grade first. Within a grade, the most scanned come first.
- **No overlap:** the two lists never share a product.
  - The graded products are ranked best first and split in halves. The better half, up to N (R7's N), is the healthiest, and an odd count's extra product goes to it.
  - The least healthy are the worst of the rest, up to N.
  - So with 2N or more graded products, they are simply the N best and the N worst.
- **Coverage:** each period also carries how many of its scans are of products with a Nutri-Score, and how many scans it has in all.

## 6. Functional requirements

### 6.1 Global

- **G1:** A prominent **location selector** appears in the header on every page. It lists `all` plus every hierarchy level from R2.
- **G2:** The selected location is held in the browser URL as `?location=<location>`. If absent, it defaults to `all`. Changing the selection keeps the user on the current page.
- **G3:** The header links to the **scanners page** (§6.4), keeping `?location`. The link reads "Scanners", or "✕ N offline" when any scanner within the selected location is offline (R6). (This replaced a header widget, in ticket 10.)

### 6.2 Index page: `/`

- **I1:** Bar chart of scans per local day across **all history**, with brush-to-zoom.
- **I2:** List of the **last 25 scans**: local date and time, location, and the product per R3. Each row links to its code page, keeping `?location`.
- **I0:** A **period selector** at the top of the page, above the chart: a tab per period (R7). The chosen period is kept in `?period=` (default `last-30-days`; unknown values fall back to it). Top scans (I3) and the healthiest and least healthy products (I4) follow it and name it in their headings, e.g. "Top scans · Last 30 days". Latest scans (I2) doesn't follow it.
- **I3:** A **Top scans** panel (R7), below the chart, for the selected period (I0). An "Unknown only" toggle, kept in `?unknown=1`, switches to the unknown-products lists. Each row shows rank, the product per R3, count and share, and links to its code page. An empty period says so.

- **I4:** A **Healthiest and least healthy products** panel (R8), below Top scans.
  - It follows the selected period (I0). "Unknown only" doesn't affect it.
  - The two lists sit side by side and stack on narrow screens. Each row shows rank, the product per R3 with its Nutri-Score badge, and the count.
  - A coverage line says e.g. "Based on the 1,204 of 2,310 scans with a Nutri-Score."
  - A period without graded products says e.g. "No products with a Nutri-Score scanned today." With only one, Least healthy says "Nothing else to compare."

Page order: period selector (I0), scans per day (I1), top scans (I3), healthiest and least healthy products (I4), latest scans (I2).

### 6.3 Code page: `/codes/:code`

- **C1:** Product info per R5, or "Unknown product" and the raw code if neither OpenFoodFacts nor the Snacker archive has the code.
- **C2:** Bar chart of scans per local day for this code.
- **C3:** Bar chart of scans per local hour of day (0–23), always 24 bars.
- **C4:** List of the last 25 scans of this code: local date and time, location.
- **C5:** C2–C4 are filtered by the selected location. C1 is global.
- **C6:** `:code` is the URL-encoded code (see §7.3).

### 6.4 Scanners page: `/scanners`

- **S1:** Lists every known scanner within the selected location (`all` shows every one), offline scanners first, then by name.
- **S2:** Each row shows:
  - status: ✓ Online / ✕ Offline, with icon and label,
  - name,
  - location,
  - last heartbeat ("X ago" with the exact time),
  - last scan ("X ago" with the product's name, tagged when it's from the Snacker archive, or its code, linking to its code page, then its Nutri-Score badge when it has one (R3); or "Never"),
  - app version.
- **S3:** It shows when the data was built. A location with no scanners says so; a missing or failed file says scanner status is unavailable.

## 7. Data contract (static JSON)

The build writes everything under `public-data/data/`. No file needs query parameters to be served.

### 7.1 Files

```
data/meta.json                                  { generated_at }
data/locations.json                             all selectable locations
data/index/by-location/{location}.json          index page data
data/scanners/by-location/{location}.json       scanners page and header link data
data/codes/{code}/product.json                  product info (global)
data/codes/{code}/by-location/{location}.json   code page scan data
```

These rules decide which files exist:

- `meta.json` and `locations.json` always exist. `locations.json` includes `all`.
- An index file and a scanners file are written for every entry in `locations.json`, including `all`.
- `codes/{code}/by-location/{location}.json` is only written for locations where that code was scanned. If the file is missing, the frontend shows zero scans.
- Every scanned code has a scans file for `all`.
- `product.json` is written for **every** scanned code, with `"product": null` when neither OpenFoodFacts nor the Snacker archive has the code, and `known` saying whether OpenFoodFacts has it. Every code named in any file has one.
- Each file sits at the path its own `code` and `location` give, encoded as in §7.3.
- No other files are written.

### 7.2 Shapes

The shapes are defined by the JSON Schema at `contract/static-json.schema.json`. It has one entry in `$defs` per file, and the rows files share are also defined once there:

| File | Document |
|---|---|
| `meta.json` | `MetaFile` |
| `locations.json` | `LocationsFile` |
| `index/by-location/{location}.json` | `IndexFile` |
| `scanners/by-location/{location}.json` | `ScannersFile` |
| `codes/{code}/product.json` | `ProductFile` |
| `codes/{code}/by-location/{location}.json` | `CodeScansFile` |

- **Generated, not hand-edited:** the schema comes from the backend's contract module (`snacker schema`), and a test fails when the committed copy is out of date.
- **Frontend types:** the frontend's types for these files (`frontend/src/contract.ts`) are generated from the schema by `npm run contract`. The frontend build and lint fail when they're out of date.
- **Strict:** every field is required, even one that may be null, and fields the schema doesn't list are rejected.
- **Versioned:** `meta.json` carries `contract_version`, a single integer (now 3: version 2 added where names come from, version 3 the grades). Bump it on any breaking change: removing, renaming or retyping a field, a field becoming nullable, a file moving, adding a field, or changing a rule in §7.1 or §7.4. Adding a field counts because the schema rejects fields it doesn't list; only a whole new file doesn't. The frontend reads `meta.json` before any other file. When the version differs from the one it was built for, every page says the data and interface are out of step instead of rendering.
- **What the schema can't express:** which files exist (§7.1) and the rules that hold across fields and files (§7.4).

### 7.3 Encoding

- `{code}` and `{location}` are file names percent-encoded like `encodeURIComponent`, **except that `:` stays literal**. So barcodes and `thailand:bangkok` stay readable, while a URL code becomes `http:%2F%2Fwww.example.com%2F…`. (Decided 2026-10-19. The cost is that `:` isn't a valid file-name character on Windows.)
- Static servers decode `%` escapes before looking up a file, so the frontend **applies the same encoding again** when fetching, still leaving `:` literal. For example, `thailand:staff room` is stored as `thailand:staff%20room.json` and requested as `thailand:staff%2520room.json`. Vite's dev server doesn't match `%3A` to a literal `:`, which is why `:` stays literal in requests too.
- Browser routes use single encoding.

### 7.4 Rules across fields and files

These hold in every build, alongside the schema (§7.2) and the file rules (§7.1):

- **Locations:**
  - Every file's `location` is selectable.
  - Every scan row is from a selectable location within the file's location.
  - Every scanner is within its file's location.
- **`daily`:**
  - Office dates, unique and oldest first.
  - Every count is positive.
- **`hourly`:**
  - Exactly hours 0–23, in order.
  - In a code scans file, `hourly` and `daily` add up to the same total, and that total isn't zero.
- **`recent`:**
  - Newest first.
  - Holds the most recent `min(total, 25)` scans.
  - In a code scans file, only that code's scans.
- **Top scans:**
  - All eight periods are present, in both `top_scans` and `top_unknown_scans`.
  - Each list has at most 10 codes, each code once, with counts positive and most first.
  - Each share is in (0, 1], and a list's shares add up to at most 1, allowing for rounding.
  - `top_unknown_scans` lists only unknown products.
- **Healthiest and least healthy products** (R8): for every period,
  - each list has at most 10 products, every one with a Nutri-Score and a positive count, and no product is in both;
  - the healthiest are split from the least healthy in halves: the healthiest hold as many products as the least healthy, or one more;
  - the healthiest are best grade first and the least healthy worst grade first, the most scanned first within a grade, and no least healthy product is graded better than a healthiest one;
  - graded scans don't exceed the period's scans, and the listed counts don't exceed the graded scans.
- **Scanners:** unique, ordered by name.
- **Names:** on scan rows, top scans and last scans, `name_source` is null exactly when the name is, and `openfoodfacts` only for a known product. The same holds for a product file's product.
- **Grades:** only a known product's product file has grades, and only a known product's scan rows, top scans and last scans have a Nutri-Score.
- **Times:**
  - `generated_at`, `scanned_at`, `last_seen` and a last scan's `scanned_at` are UTC, written like `2026-10-19T12:00:00Z`.
  - A scan row's `office_time` is the same moment as its `scanned_at`, written with the UTC offset its `office_time_zone` (an IANA name) had then.

The backend's `check` module tests a built output against all of §7, and names the file behind each violation.

## 8. Technical design

### 8.1 Backend (`backend/`, Python, Polars, uv)

The backend is a CLI with no running server and these commands:

- `snacker extract-products --raw … --food … --products … [--archive …] [--force]`: `--archive` is the Snacker archive CSV. It is merged whenever the products table is written; without it, names come from OpenFoodFacts only. Codes the archive records twice are reported.
- `snacker build --raw … --products … --out …`: it publishes only output that passes the contract check (§7.4). Otherwise it lists the violations and leaves the previous data in place.
- `snacker check --out …`: runs the contract check on its own.
- `snacker schema --out …`: regenerates `contract/static-json.schema.json`.

Inside, each step is a named function with explicit inputs and outputs, so it can become a Dagster asset later:

| Step (module) | Input | Output |
|---|---|---|
| Product extraction (`products`) | `food.parquet`, scanned codes, Snacker archive (optional) | `products.parquet`: one row per scanned code, with `known` false for unknown products, `name_source` naming where each name came from, and the product's grades |
| Scan normalisation (`scans`) | raw scan files | scans table (R1) |
| Heartbeat normalisation (`heartbeats`) | raw heartbeat files | heartbeats table, then scanner statuses (R6) |
| Locations (`locations`) | scans, time zone map | selectable locations, scans within a location, office time zones |
| Scan summary (`scan_summary`) | scans with office time zones and products | daily, hourly and recent (`summarise`); top scans (`top_scans`, R7) |
| Build (`build`) | raw files, products table, config, build time | JSON files (§7) |

- `extract-products` reruns only when there are unseen codes, when the table predates a column change, or with `--force`. This keeps normal builds off the 8 GB file.
- `build` runs the normalisation steps itself and never reads `food.parquet`. Codes scanned since the last extraction count as unknown products.
- Configuration (`config.py`) holds the time zone prefix map, the recent-list size (25) and the top-scans size (10). Input and output paths are CLI arguments.
- Product images are hotlinked from OpenFoodFacts (docs/adr/0001).

### 8.2 Frontend (`frontend/`)

- Vite, React, TypeScript, React Router (`/`, `/codes/:code`, `/scanners`).
- Charts use Vega-Lite via `react-vega`.
- Node 22 LTS, pinned in `.nvmrc`.
- In development, Vite serves `public-data/` as static files.

### 8.3 Repository

- A monorepo initialised with `git init`, containing `backend/`, `frontend/`, `PRD.md` and `project.md`.
- `data/` and `public-data/` are git-ignored.

## 9. Testing

Backend tests run against small fixture files, never the real data. They sit at five seams:

- the end-to-end build (fixture raw files → the JSON tree)
- product extraction (a fixture food parquet → the products table)
- Scan summary (`summarise`)
- top scans (`top_scans`)
- Locations

They cover:

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
  - Top scans: each period's boundaries (including zones that disagree about the day), ties, the size limit and share.
  - A scanner's last scan by API key.
- **Output contract**
  - A fixture build writes the expected paths, including URL-encoded codes and locations.
  - The JSON matches the expected shapes, including `product: null` and 24-entry `hourly`.

Frontend tests are out of scope for this phase.

## 10. Future / open

- Range toggle or weekly/monthly roll-ups on the index chart, if the all-history daily chart proves hard to read.
- Telemetry (wifi RSSI, uptime, free memory, reset cause) on the scanners page.
- The scanner name in the scan payload (a firmware change), which would replace the API-key link (docs/adr/0002).
- Nutrients on code pages.
- Frontend component tests.
- Moving the build into Dagster, reading from S3.

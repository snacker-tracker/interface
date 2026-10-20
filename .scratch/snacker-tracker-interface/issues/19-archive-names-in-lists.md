# 19: The Snacker archive names products in the lists

**What to build:** names from the Snacker archive (GLOSSARY.md) fill in where OpenFoodFacts has none. The archive is the previous Snacker Tracker's product records, a frozen CSV (`data/codes.csv`).

Top scans, Latest scans and the scanners page's last scan show these names with a small "Snacker archive" tag. OpenFoodFacts names stay untagged. An unknown product is still one OpenFoodFacts doesn't have. When the archive names an unknown product, its row shows the name, the tag and "Add it to OpenFoodFacts", and no code. On the real data, about 98 unknown products and the 10 known products without a name gain names. Requested 2026-10-20.

**Blocked by:** 18 (Scan rows say whether their product is known).

**Status:** ready-for-agent

Decisions from the design session:

- Only the archive's `name` is used. Its `url`, `categories` and timestamps are ignored.
- **Precedence:** an OpenFoodFacts name wins whenever there is one, and the archive only fills a missing name. Some archive names are wrong for their barcode (for example "Hot Pants" for a can of Pringles), which is why OpenFoodFacts comes first.
- **Codes:** archive codes are matched to scanned codes exactly, odd ones like `8 858985 300118` and `ub` included. Names are trimmed.
- **Duplicates:** a code with more than one archive row (`5` and `78` today) gets no archive name, and the extraction reports it.
- **Pipeline:**
  - `extract-products` takes an optional `--archive` and merges whenever it writes the products table.
  - The table gains a `name_source` column. This is a column change, so the existing table is re-extracted once without `--force`.
  - `build`'s inputs don't change.
  - The archive is frozen, so there's nothing to detect when it changes. An extraction run without `--archive` leaves archive names out until the next one run with it; the README says so.
- **Contract (still version 2):** `name_source`, either `"openfoodfacts"` or `"snacker-archive"`, sits beside the name on top scans, scan rows and last scans. It is null exactly when the name is null, and the check enforces that.

- [ ] `extract-products --archive` merges archive names under the precedence rule and records each name's source, and it reports duplicated codes that were dropped.
- [ ] Without `--archive`, the table has OpenFoodFacts names only, each marked with its source.
- [ ] Top scans, scan rows and last scans in the JSON carry `name_source`, and the schema, the check and the generated frontend types cover it.
- [ ] Top scans, Latest scans and the scanners page's last scan tag archive names with "Snacker archive". An archive-named unknown product keeps "Add it to OpenFoodFacts", and no row with a name shows its code.
- [ ] The tests cover:
  - an OpenFoodFacts name beating an archive name
  - an archive name filling an unknown product
  - an archive name filling a known product without a name
  - a duplicated archive code dropped
  - no archive given
  - `name_source` flowing through to the built JSON
- [ ] The real data builds, and the build's check passes.
- [ ] PRD (§4 sources, R3, I2, I3, S2, §8.1) and the backend README describe the archive.

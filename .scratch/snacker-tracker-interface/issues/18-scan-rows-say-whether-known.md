# 18: Scan rows say whether their product is known

**What to build:** each scan in the latest-scans lists, and each scanner's last scan, says whether OpenFoodFacts has its product. The latest-scans list can then treat a product without a name the way Top scans does: an unknown product gets "Add it to OpenFoodFacts", and a product OpenFoodFacts has but without a name gets "On OpenFoodFacts". Today it can't tell the two apart (PRD §10). This ticket is a prefactor for the Snacker archive work (tickets 19 and 20), and it starts contract version 2. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Scan rows and last scans carry `known`, and the schema requires it.
- [x] `contract_version` is 2. Tickets 19 and 20 extend version 2 without bumping again; deploy once, after 20.
- [x] The committed schema and the frontend's generated types are regenerated.
- [x] The build's check still passes on the real data.
- [x] In Latest scans, a product OpenFoodFacts has but without a name links to its OpenFoodFacts page ("On OpenFoodFacts"), and an unknown product with a barcode links to "Add it to OpenFoodFacts".
- [x] A build test covers `known` on a scan row and on a last scan, for both a known and an unknown product.
- [x] PRD R3 and §10 no longer describe the latest-scans gap.

## Comments

- 2026-10-20: Implemented.
  - **Contract:** `known` is added to scan rows and last scans, and `contract_version` is 2. The schema and the frontend types are regenerated.
  - **Frontend:** Latest scans passes each row's `known` to the shared product cell, so a nameless product OpenFoodFacts has now gets "On OpenFoodFacts". The scanners page doesn't use `known` yet; ticket 19 adds the archive tag there.
  - **Tests:** a build test covers `known` for a named product, a nameless known product and an unknown product, on scan rows and last scans. Existing exact-shape expectations gained the field.
  - **PRD:** R3 and §10 no longer mention the gap, and §7.2 says version 2.
  - **Checked:** the real data builds and passes the check, with `known` in the output. The UI wasn't checked in a browser.

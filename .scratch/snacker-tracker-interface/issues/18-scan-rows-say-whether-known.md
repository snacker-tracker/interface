# 18: Scan rows say whether their product is known

**What to build:** each scan in the latest-scans lists, and each scanner's last scan, says whether OpenFoodFacts has its product. The latest-scans list can then treat a product without a name the way Top scans does: an unknown product gets "Add it to OpenFoodFacts", and a product OpenFoodFacts has but without a name gets "On OpenFoodFacts". Today it can't tell the two apart (PRD §10). This ticket is a prefactor for the Snacker archive work (tickets 19 and 20), and it starts contract version 2. Requested 2026-10-20.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Scan rows and last scans carry `known`, and the schema requires it.
- [ ] `contract_version` is 2. Tickets 19 and 20 extend version 2 without bumping again; deploy once, after 20.
- [ ] The committed schema and the frontend's generated types are regenerated.
- [ ] The build's check still passes on the real data.
- [ ] In Latest scans, a product OpenFoodFacts has but without a name links to its OpenFoodFacts page ("On OpenFoodFacts"), and an unknown product with a barcode links to "Add it to OpenFoodFacts".
- [ ] A build test covers `known` on a scan row and on a last scan, for both a known and an unknown product.
- [ ] PRD R3 and §10 no longer describe the latest-scans gap.

# 01: Spike: reading raw events from S3 and OpenFoodFacts from Hugging Face

**What to build:** time-boxed measurements, on the real data, of the two reads the AWS deployment depends on. They decide whether 02 and 03 read directly or copy to local disk first. This came from the design session on 2026-10-20 (ADRs 0003–0006).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- **Raw events:** can a Polars `s3://` glob over the raw bucket's scanner prefix (about 11.5k small objects, 51 MB) read the scans and heartbeats well within a 15-minute Lambda run, with about 1–2 GB of memory? If not, how long does copying the prefix to /tmp take?
- **OpenFoodFacts:** how long, and with how much memory, does a lazy Polars scan of `hf://datasets/openfoodfacts/product-database/food.parquet` take for about 850 codes? The codes aren't sorted, so expect it to read the whole `code` column.
- **Where to measure:** from a laptop, and if possible from a Lambda-sized environment (same region, similar memory).

- [ ] Timings and peak memory for both reads are written in this ticket's comments, with the environment they were taken in.
- [ ] A recommendation for each read: direct, or copy first. For OpenFoodFacts, also say whether it fits a 15-minute Lambda.
- [ ] No production code changes. Throwaway scripts stay out of the repo, or in a clearly marked scratch place.

## Comments

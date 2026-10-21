# 01: Spike: reading raw events from S3 and OpenFoodFacts from Hugging Face

**What to build:** time-boxed measurements, on the real data, of the two reads the AWS deployment depends on. They decide whether 02 and 03 read directly or copy to local disk first. This came from the design session on 2026-10-20 (ADRs 0003–0006).

**Blocked by:** None (can start immediately).

**Status:** resolved

- **Raw events:** can a Polars `s3://` glob over the raw scanner bucket (`snacker-tracker-prod`, about 11.5k small objects, 51 MB) read the scans and heartbeats well within a 15-minute Lambda run, with about 1–2 GB of memory? If not, how long does copying the prefix to /tmp take?
- **OpenFoodFacts:** how long, and with how much memory, does a lazy Polars scan of `hf://datasets/openfoodfacts/product-database/food.parquet` take for about 850 codes? The codes aren't sorted, so expect it to read the whole `code` column.
- **Where to measure:** from a laptop, and if possible from a Lambda-sized environment (same region, similar memory).

- [x] Timings and peak memory for both reads are written in this ticket's comments, with the environment they were taken in.
- [x] A recommendation for each read: direct, or copy first. For OpenFoodFacts, also say whether it fits a 15-minute Lambda.
- [x] No production code changes. Throwaway scripts stay out of the repo, or in a clearly marked scratch place.

## Comments

### 2026-10-20: results

**Environment:** a laptop in Thailand (16 cores, 60 GiB) on a home connection. Polars 2.0.0. The raw bucket is in ap-southeast-1. No Lambda-sized environment was measured. Peak memory is the process's peak RSS. The scripts are throwaway and stayed out of the repo.

#### Raw events (`snacker-tracker-prod/raw/data/scanner`)

There are 11,832 objects (415 scans, 11,416 heartbeats), totalling 11.4 MB. The ticket's 51 MB is their size on disk, rounded up per file.

| Read | Time | Peak |
| --- | --- | --- |
| Polars `s3://` glob, as `read_events` does it (two runs) | scans 4.2–4.4 s, heartbeats 106–110 s: **110–114 s** | 551–601 MB |
| Copy first: `aws s3 sync`, default 10 parallel requests | 70 s, then 0.4 s to read | 511 MB |
| Copy first: `aws s3 sync`, 64 parallel requests | **21 s**, then 0.4 s to read | 511 MB |

Heartbeats are almost all of it: about 6,000 new objects a month (6,054 in September, 5,362 in October up to the 20th). The direct read costs about 9 ms per object, so it grows by about a minute a month and would pass 15 minutes in roughly a year. A parallel copy costs about 2 ms per object.

**Recommendation: copy first,** with a parallel download (a thread pool over `list_objects_v2`, about 64 workers) into `/tmp`, then read locally as today. It's 5× faster now and stays well inside a Lambda run for years. 52 MB fits the default 512 MB `/tmp`. Compacting old heartbeats would remove the growth altogether, but that's a separate decision.

#### OpenFoodFacts (`hf://datasets/openfoodfacts/product-database/food.parquet`, 7.96 GB)

The read is `extract_products`'s query: 10 columns, 854 codes.

| Read | Time | Peak |
| --- | --- | --- |
| Local copy of the file (baseline) | 1.0 s, 508 found | 748 MB |
| `hf://`, anonymous (two runs) | **failed after 73 s and 150 s: HTTP 429** | — |
| The signed CDN URL, resolved once (two runs) | **131 s and 123 s**, 508 found | 1.33–1.38 GB |
| Plain download of the file from the CDN | 11 MB/s here, so about 12 min for the whole file | — |

- **Why `hf://` fails:** every range request goes through `huggingface.co/…/resolve/main/food.parquet`. Anonymous IPs get a fixed window of 3,000 resolver requests per 5 minutes (header `ratelimit-policy: "fixed window";"resolvers";q=3000;w=300`). One scan uses all of them and is still not finished. A Lambda outside a VPC also shares its outbound IPs with other AWS customers.
- **The workaround:** a `HEAD` on the resolve URL returns a 302 to a signed URL on `us.aws.cdn.hf.co`. Scanning that `https://` URL makes one resolver request. Every range read after that goes to the CDN, with no rate-limit errors.
- **Region:** the CDN host is in the US, and the Lambda will be in ap-southeast-1. Lambda's bandwidth is unmeasured, but should be at least as good as this connection.

**Recommendation: read directly, through the signed URL.**
- Resolve the URL once per run, then `pl.scan_parquet(signed_url)`. Pass an `HF_TOKEN` too for a higher quota, if a token is available.
- **It fits a 15-minute Lambda,** at about 2 minutes here. Give the extraction function **3 GB** of memory: the measured peak was 1.4 GB, and Lambda's CPU scales with memory.
- Copying first isn't worth it: about 12 minutes for 8 GB at this connection's speed, and it wouldn't fit the default `/tmp`.

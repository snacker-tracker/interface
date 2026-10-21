# 08: Prod goes live after an approval

**What to build:** after an approval, prod runs exactly what dev ran, served through CloudFront on `khanom.xyz` and `www.khanom.xyz`.

**Blocked by:** 07 (CI deploys dev on push to main).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0003–0006):

- **The prod job:** it runs in a `prod` GitHub environment with required reviewers, using the prod CI role.
- **What it promotes:** the image digest and frontend build that dev deployed for the same commit. Prod never builds its own image.
- **Its steps:** `terraform apply` in the `prod` workspace (with `prod.tfvars`), update the functions to the digest, invoke one build, then sync the frontend outside `data/`.
- **The prod site bucket** (`snacker-tracker-prod-site`) comes from the admin configuration's prod workspace, private behind Origin Access Control as in dev. Nothing in the main configuration changes its policy.
- **Hostnames:** `khanom.xyz` (the apex) and `www.khanom.xyz` both serve the site from one distribution. One ACM certificate (us-east-1) covers both names and is validated through the `khanom.xyz` zone (`Z0781732PCOBWRVFR9YS`). Each name gets A/AAAA alias records.
- **The cut-over:** the records move to the new distribution only once it serves correctly. Before switching, check it on its `cloudfront.net` address. If either name has records today, note them in this ticket's comments before changing them.
- **Before the first deploy,** check that the site bucket uses default S3 encryption, not KMS (ADR 0004).

- [ ] An approved run promotes dev's digest and frontend build to prod, and an unapproved one does nothing.
- [ ] The distribution serves the site correctly on its `cloudfront.net` address before the domain moves.
- [ ] After the cut-over, `khanom.xyz` and `www.khanom.xyz` serve data built every 15 minutes, and the scanners page's "Data built X ago" stays current.
- [ ] Rolling back means re-running the job for an earlier commit, and this is documented.

## Comments

**2026-10-21: groundwork.**
- The prod admin workspace is applied (ticket 05); the prod site bucket is AES256, not KMS.
- `infra/main/prod.tfvars` holds the prod role ARNs.
- **Existing records:** before the cut-over the `khanom.xyz` zone has only NS and SOA at the apex and nothing for `www`, so no A/AAAA records are overwritten.

**Still to do:**
- a `prod` GitHub environment with required reviewers;
- the prod job;
- the first approved run, checked on `cloudfront.net` first.

**2026-10-21: prod job written, not yet run.**
- **The split:** `.github/workflows/dev.yml` became `pipeline.yml`. It runs backend and frontend, then `image` (pushed once, in the dev environment), then `dev`, then `prod`. Both deploy jobs call `deploy.yml` with the same digest and the `frontend-<sha>` artifact.
- **`deploy.yml`** picks the GitHub environment, the CI role `snacker-tracker-<env>-ci`, `TF_WORKSPACE` and `<env>.tfvars` from its `environment` input.
- **The cut-over:** `serve_hostnames` (default true) gates the A/AAAA records. `prod.tfvars` sets it to false for now; the certificate and its validation records are created either way. A new output, `distribution_domain`, goes in the job summary, so the `cloudfront.net` address can be checked first.
- **Workspace:** created the main configuration's `prod` workspace by hand, so `TF_WORKSPACE=prod` finds it.
- **Planned locally as admin:**
  - dev: only the new output;
  - prod: 14 to create (functions, schedule, working bucket, OAC, distribution, certificate and its two validation records), no A/AAAA.
- **Rollback:** documented in `backend/README.md` as re-running `prod / deploy` on an earlier commit's run (re-runs are allowed for 30 days; artifacts are kept for 90).

**Still to do:**
- Create the `prod` GitHub environment with required reviewers.
- After the first prod apply, upload the Snacker archive to `s3://snacker-tracker-prod-working/snacker-archive.csv` by hand, as in dev. Until then the extraction the first build starts fails, and each scheduled build starts it again.
- Check `https://<distribution_domain>`, then set `serve_hostnames = true` and run again.

**2026-10-21: first prod run, approved, deployed without the hostnames.**
- **Distribution:** `E19OZ4WNBAMAKB`, `d3d09dryz2ybdk.cloudfront.net`, with aliases `khanom.xyz` and `www.khanom.xyz`.
- **Build:** published 3,466 files on the first run, then 5 on the next.
- **Extraction:** failed twice before the archive was there, as expected. I then uploaded `data/codes.csv` as `s3://snacker-tracker-prod-working/snacker-archive.csv` and started one extraction: 854 codes in 111 s, 1.48 GB peak, `products.parquet` written.
- **Checked on `cloudfront.net`:**
  - `/` and `/codes/8851959132012`: 200, HTML, no-cache;
  - `data/*.json`: 200, `max-age=60`;
  - HTTP redirects with a 301 to HTTPS.
- **Cut-over:** removed `serve_hostnames = false` from `prod.tfvars`. The prod plan adds the four A/AAAA records and nothing else. It takes effect on the next approved prod run.

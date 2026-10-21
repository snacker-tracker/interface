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

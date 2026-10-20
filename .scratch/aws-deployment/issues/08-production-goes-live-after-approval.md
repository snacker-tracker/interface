# 08: Production goes live after an approval

**What to build:** after an approval, production runs exactly what staging ran, served through CloudFront on the production domain.

**Blocked by:** 07 (CI deploys staging on push to main).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0003–0006):

- **The production job:** it runs in a `production` GitHub environment with required reviewers, using the production CI role.
- **What it promotes:** the image digest and frontend build that staging deployed for the same commit. Production never builds its own image.
- **Its steps:** `terraform apply` for production, update the functions to the digest, invoke one build, then sync the frontend outside `data/`.
- **The production site bucket** already exists and is used as it is: its website endpoint is CloudFront's origin, and nothing changes its policy.
- **The cut-over:** the production domain's alias moves to the new distribution only once it serves correctly. Before switching, check it on its `cloudfront.net` address.
- **Before the first deploy,** check that the site bucket uses default S3 encryption, not KMS (ADR 0004).

- [ ] An approved run promotes staging's digest and frontend build to production, and an unapproved one does nothing.
- [ ] The distribution serves the site correctly on its `cloudfront.net` address before the domain moves.
- [ ] After the cut-over, the production domain serves data built every 15 minutes, and the scanners page's "Data built X ago" stays current.
- [ ] Rolling back means re-running the job for an earlier commit, and this is documented.

## Comments

# 07: CI deploys staging on push to main

**What to build:** pushing to main tests the code and deploys it to staging with no manual steps, so staging always runs main.

**Blocked by:** 06 (Staging runs on Lambda behind CloudFront).

**Status:** ready-for-agent

Decisions from the design session (ADRs 0005, 0006):

- **The workflow** is GitHub Actions, using the staging CI role through OIDC in the `staging` GitHub environment.
- **The steps, in order:**
  1. Backend tests and mypy, frontend lint and build.
  2. Build the image once and push it to the shared ECR repository, tagged with the commit SHA.
  3. `terraform apply` for staging.
  4. Update both functions to the image's digest.
  5. Invoke one build, so the data matches the new contract version.
  6. Sync the frontend's built files to the site bucket: long cache for hashed assets, no-cache for `index.html`, and nothing under `data/`.
- **Pull requests** get a `terraform plan` for staging, run with read-only use of the same role.
- **Contract mismatch:** between steps 5 and 6 a page may show the designed "data and interface are out of step" message for a few seconds.

- [ ] A push to main deploys staging end to end, and a failing test stops it before anything is deployed.
- [ ] The workflow never writes under `data/`, and the role's explicit deny would stop it if it tried.
- [ ] Pull requests show a staging plan.
- [ ] The image is built once per commit, and its digest is recorded so that 08 can promote it.

## Comments

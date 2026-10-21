# 07: CI deploys dev on push to main

**What to build:** pushing to master tests the code and deploys it to dev with no manual steps, so dev always runs master. (The branch stays `master`; the title says main from before that was decided.)

**Blocked by:** 06 (Dev runs on Lambda behind CloudFront).

**Status:** in-progress (written; waiting for the repo on GitHub)

Decisions from the design session (ADRs 0005, 0006):

- **The workflow** is GitHub Actions, using the dev CI role through OIDC in the `dev` GitHub environment.
- **The steps, in order:**
  1. Backend tests and mypy, frontend lint and build.
  2. Build the image once and push it to the shared ECR repository, tagged with the commit SHA.
  3. `terraform workspace select dev`, then `terraform apply -var-file=dev.tfvars`.
  4. Update both functions to the image's digest.
  5. Invoke one build, so the data matches the new contract version.
  6. Sync the frontend's built files to the site bucket: long cache for hashed assets, no-cache for `index.html`, and nothing under `data/`.
- **Pull requests** get a `terraform plan` in the `dev` workspace, run with read-only use of the same role.
- **Contract mismatch:** between steps 5 and 6 a page may show the designed "data and interface are out of step" message for a few seconds.

- [ ] A push to master deploys dev end to end, and a failing test stops it before anything is deployed.
- [ ] The workflow never writes under `data/`, and the role's explicit deny would stop it if it tried.
- [ ] Pull requests show a dev plan.
- [ ] The image is built once per commit, and its digest is recorded so that 08 can promote it.

## Comments

**2026-10-21: workflow written, not yet run.** `.github/workflows/dev.yml`:
- `backend` (uv, mypy, pytest) and `frontend` (lint, build, artifact `frontend-<sha>` kept 90 days) run on every push and PR.
- `plan` (PRs): assumes the dev CI role without an environment (OIDC subject `pull_request`), then `terraform plan -lock=false` against the image dev runs now; the plan goes in the job summary.
- `deploy` (push to master, environment `dev`, one at a time; needs both test jobs):
  - `backend/scripts/push-image.sh` builds once per commit and reuses an image already tagged with the SHA;
  - `terraform apply` points both functions at the digest;
  - it waits on both functions and invokes one build, failing on a function error;
  - `frontend/scripts/sync-site.sh` uploads new assets, then `index.html` (no-cache, excluding `data/*`), then prunes old assets.

The digest is in the job summary, and the commit's ECR tag leads to it for 08.

**Checked locally, not yet in CI:**
- actionlint and shellcheck pass.
- The sync was dry-run and then run against the dev site: no keys under `data/`, and the headers are right.
- The lock-free plan shows only new outputs.
- The IAM simulator allows every read and write the jobs make, and explicitly denies `data/*` writes.

**Before the first run:**
- Push to `snacker-tracker/interface` (the branch stays `master`, which the workflow triggers on).
- Create the `dev` environment.

**Open:** PRs plan with the full CI role, as the trust policy allows. "Read-only" is only how the job uses it. PRs from forks get no OIDC token, so their plan job fails.

**2026-10-21: first PR run failed at login, fixed.**
- **Cause:** GitHub's OIDC subject carries the owner's and repo's numeric IDs, `repo:snacker-tracker@59108816/interface@1428184726:pull_request` (seen in CloudTrail). The trust policy expected `repo:snacker-tracker/interface:…`.
- **Fix:** the `github_repo` default in `infra/admin` is now the ID form. Applied in dev: the CI role's trust changed in place. Prod's admin apply picks it up.

**2026-10-21: second PR run failed at `terraform init`, fixed.**
- **Cause:** `init` in the default workspace checks the bare key `snacker-tracker-interface`. The CI role is allowed only `env:/dev/…`, so S3 returned 403 on HeadObject.
- **Fix:** the workflow now sets `TF_WORKSPACE=dev`, so `init` starts in dev, and the `workspace select` steps are gone.

# IAM roles and site buckets are created by an admin; CI only passes known roles

CI runs `terraform apply`, so its role must not be able to widen its own permissions or anyone else's. The repo therefore has two Terraform configurations:
- **An admin configuration, applied by hand by someone with IAM rights.** For each environment it creates:
  - a CI role, trusted only for that GitHub environment's OIDC subject;
  - the build, extraction and scheduler roles, each with least-privilege policies;
  - the staging site bucket and its website policy.
- **The main configuration, applied by CI.** Its role can manage only resources named `snacker-tracker-<env>-*`, or tagged `project=snacker-tracker` where AWS generates the ID (CloudFront, ACM).
  - It can change only records in the one hosted zone, and only its own key in the state bucket.
  - On IAM it has only `GetRole` and `PassRole`, for its environment's known roles and to the intended services. It cannot create, attach or alter any permission, or any bucket policy.

The cost is that any new permission needs an admin apply first. That covers a Lambda needing more access, and Terraform starting to manage a new kind of resource. Until then, the plan fails with an access error. We accept that friction in exchange for CI never being able to escalate.

# The ECR repository is shared and managed outside this repo

Several environments use the backend's container image (dev and prod at least), so its ECR repository is managed outside this repo, including its lifecycle rules. This repo refers to it by URL. It lives in the same AWS account as the environments.

Each image is built once, in dev's pipeline, tagged with its short commit SHA (the full one is in its labels since 2026-11-01), and deployed to each environment by digest. Prod therefore runs exactly the image dev ran.

The dev CI role may push to that one repository. The prod CI role may only read it, which is all it needs to point its Lambdas at an existing digest.

Each deploy also tags the image it deployed `<environment>-<UTC time>`, so the lifecycle rules keep the images an environment ran recently and expire the rest (2026-11-01). For that, the prod CI role may put an image manifest too, but not upload layers, so it can only tag an image dev already pushed.

Until it moves there, the admin configuration's dev workspace creates the repository (`snacker-tracker-lambda/interface`) and its policy (2026-10-20). Moving it later means removing it from this state, not recreating it.

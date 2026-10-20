# The ECR repository is shared and managed outside this repo

Several environments use the backend's container image (staging and production at least), so its ECR repository is managed outside this repo, including its lifecycle rules. This repo refers to it by URL. It lives in the same AWS account as the environments.

Each image is built once, in staging's pipeline, tagged with its commit SHA, and deployed to each environment by digest. Production therefore runs exactly the image staging ran.

The staging CI role may push to that one repository. The production CI role may only read it, which is all it needs to point its Lambdas at an existing digest.

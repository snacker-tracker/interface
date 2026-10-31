# stepdag renders a manifest, and Terraform deploys it

stepdag does not deploy anything. From a graph's definitions it renders a manifest: a JSON file holding the state machine's definition and, for each asset, its handler, memory, timeout, ephemeral storage, retry policy and role name. Terraform reads it and creates one Lambda per asset with `for_each`, all from the same image. Adding an asset then needs no Terraform change, unless it needs a role that doesn't exist yet.

Each step retries only transient Lambda errors by default, twice with backoff. An error raised by the asset's function, or a failed check, is not retried, because it would fail the same way again. An asset can opt into retrying its own errors, for example on a flaky download.

Every asset is a Lambda, so each is limited to 15 minutes and 10 GB of memory. Because steps exchange only pointers, a second kind of compute can be added later without changing assets. An ECS task started by Step Functions' `.sync` integration is the obvious one.

## Considered options

- **stepdag deploying itself through the AWS API.** Rejected: where CI changes AWS only through Terraform, and must never be able to change roles or permissions, as in the repository stepdag started in, a framework that deploys itself would bypass both.
- **Terraform written by hand for each asset.** Rejected: it drifts from the code.
- **ECS tasks for heavy assets from the start.** Rejected for now: a cluster, task definitions and networking are a lot to add before any asset has outgrown a Lambda.

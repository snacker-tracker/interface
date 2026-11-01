locals {
  env    = terraform.workspace
  prefix = "snacker-tracker-${local.env}"

  # The admin configuration's policies are written against these names (infra/admin/README.md).
  site_bucket    = "${local.prefix}-site"
  working_bucket = "${local.prefix}-working"
}

resource "terraform_data" "workspace" {
  lifecycle {
    precondition {
      condition     = contains(["dev", "prod"], local.env)
      error_message = "Select the dev or prod workspace; names come from it."
    }
  }
}

# The products table and the Snacker archive. Private and SSE-S3 by S3's defaults; the CI
# role may not change bucket policies or public access (ADR 0005).
resource "aws_s3_bucket" "working" {
  bucket = local.working_bucket
}

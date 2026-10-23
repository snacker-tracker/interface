locals {
  env    = terraform.workspace
  prefix = "snacker-tracker-${local.env}"

  # The admin configuration's policies are written against these names (infra/admin/README.md).
  site_bucket      = "${local.prefix}-site"
  working_bucket   = "${local.prefix}-working"
  build_function   = "${local.prefix}-build"
  extract_function = "${local.prefix}-extract"

  settings = {
    SNACKER_RAW              = "s3://${var.raw_bucket}/raw/data/scanner"
    SNACKER_PRODUCTS         = "s3://${local.working_bucket}/products.parquet"
    SNACKER_ARCHIVE          = "s3://${local.working_bucket}/snacker-archive.csv"
    SNACKER_SITE             = "s3://${local.site_bucket}"
    SNACKER_EXTRACT_FUNCTION = local.extract_function
    # The scans and heartbeats earlier builds read, stamped with the image that wrote them (ADR 0011).
    SNACKER_CACHE        = "s3://${local.working_bucket}/cache"
    SNACKER_CODE_VERSION = split("@", var.image_uri)[1]
  }
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

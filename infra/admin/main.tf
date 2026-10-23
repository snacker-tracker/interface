data "aws_caller_identity" "current" {}

locals {
  env     = terraform.workspace
  account = data.aws_caller_identity.current.account_id
  prefix  = "snacker-tracker-${local.env}"

  # Names the main configuration must use: the policies below are written against them.
  site_bucket       = "${local.prefix}-site"
  working_bucket    = "${local.prefix}-working"
  build_function    = "${local.prefix}-build"
  extract_function  = "${local.prefix}-extract"
  products_key      = "products.parquet"
  archive_key       = "snacker-archive.csv"
  cache_prefix      = "cache/"
  ecr_repository    = "arn:aws:ecr:${var.region}:${local.account}:repository/${var.ecr_repository_name}"
  function_arn      = "arn:aws:lambda:${var.region}:${local.account}:function"
  log_group_arn     = "arn:aws:logs:${var.region}:${local.account}:log-group:/aws/lambda"
  site_bucket_arn   = "arn:aws:s3:::${local.site_bucket}"
  role_arn          = "arn:aws:iam::${local.account}:role"
  github_oidc       = "arn:aws:iam::${local.account}:oidc-provider/token.actions.githubusercontent.com"
  main_state_object = "env:/${local.env}/${var.main_state_key}"

  # Access logs (ADR 0010). CloudFront's log delivery is set up in us-east-1 whatever the bucket's Region.
  access_logs_bucket     = "${local.prefix}-access-logs"
  access_logs_bucket_arn = "arn:aws:s3:::${local.access_logs_bucket}"
  access_logs_s3_prefix  = "cloudfront"
  log_delivery_arn       = "arn:aws:logs:us-east-1:${local.account}"
  access_log_group_arn   = "${local.log_delivery_arn}:log-group:/aws/vendedlogs/cloudfront/${local.prefix}-*"
}

resource "terraform_data" "workspace" {
  lifecycle {
    precondition {
      condition     = contains(["dev", "prod"], local.env)
      error_message = "Select the dev or prod workspace; names and policies come from it."
    }
  }
}

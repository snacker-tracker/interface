# The graph (snacker.graph) on Step Functions, as container-image Lambdas: the stepdag scans
# example's stack (scans ticket 05), applied by hand until #121 replaces it. Everything
# per asset comes from manifest.json (`stepdag manifest snacker.graph.definitions:defs`): nothing here
# names an asset.

locals {
  env             = terraform.workspace
  prefix          = "stepdag-scans-${local.env}"
  # The shared image repository (ADR 0006) lets Lambda pull only for functions named
  # snacker-tracker-*, so the functions are named for Snacker rather than the stack (#118).
  function_prefix = "snacker-tracker-${local.env}-graph-"
  manifest        = jsondecode(file("${path.module}/manifest.json"))

  # Snacker's prod raw scanner events: read-only, never written.
  raw_bucket = "snacker-tracker-prod"
  raw_prefix = "raw/data/scanner/"
}

resource "terraform_data" "workspace" {
  lifecycle {
    precondition {
      condition     = local.env == "dev"
      error_message = "Select the dev workspace; names come from it."
    }
  }
}

data "aws_caller_identity" "current" {}

# The image's repository. Applied alone first (-target), before any image exists.
resource "aws_ecr_repository" "scans" {
  name         = "stepdag-scans"
  force_delete = true
}

# The example's Delta tables. Private; a toy, so it can be destroyed with its contents.
resource "aws_s3_bucket" "tables" {
  bucket        = "${local.prefix}-tables"
  force_destroy = true
}

# OpenFoodFacts copies are 8 GB each and named by revision; a reader only ever needs a recent one.
# A failed copy's multipart upload is aborted by boto3, and expired here if the Lambda died first.
resource "aws_s3_bucket_lifecycle_configuration" "tables" {
  bucket = aws_s3_bucket.tables.id

  rule {
    id     = "expire-openfoodfacts-copies"
    status = "Enabled"
    filter {
      prefix = "files/openfoodfacts/"
    }
    expiration {
      days = 14
    }
  }

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# The shadow site (parity ticket 09): site_tree publishes Snacker's tree into its data/ prefix.
# Private, data only; parity reports go to the tables bucket's json/runs/ prefix.
resource "aws_s3_bucket" "site" {
  bucket        = "${local.prefix}-site"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "tables" {
  bucket                  = aws_s3_bucket.tables.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# One role per manifest role, for the functions.
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "function" {
  for_each           = toset(local.manifest.roles)
  name               = "${local.prefix}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "function_logs" {
  for_each   = aws_iam_role.function
  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "function" {
  statement {
    sid       = "TablesList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.tables.arn]
  }
  statement {
    sid = "TablesReadWrite"
    # AbortMultipartUpload: a failed OpenFoodFacts copy cleans up its upload.
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.tables.arn}/*"]
  }
  statement {
    sid       = "SiteList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.site.arn]
  }

  statement {
    sid       = "SiteReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]
  }

  # Read-only on prod: no Put, Delete or anything else on the raw bucket.
  statement {
    sid       = "RawRead"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.raw_bucket}/${local.raw_prefix}*"]
  }
  statement {
    sid       = "RawList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.raw_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.raw_prefix}*"]
    }
  }
}

resource "aws_iam_role_policy" "function" {
  for_each = aws_iam_role.function
  name     = "tables-and-raw"
  role     = each.value.id
  policy   = data.aws_iam_policy_document.function.json
}

resource "aws_cloudwatch_log_group" "function" {
  for_each          = local.manifest.functions
  name              = "/aws/lambda/${local.function_prefix}${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "function" {
  for_each = local.manifest.functions

  function_name = "${local.function_prefix}${each.key}"
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = aws_iam_role.function[each.value.role].arn
  memory_size   = each.value.memory
  timeout       = each.value.timeout
  architectures = ["x86_64"]

  image_config {
    command = [each.value.handler]
  }

  ephemeral_storage {
    size = each.value.ephemeral_storage
  }

  environment {
    variables = merge(each.value.environment, {
      SCANS_TABLES        = "s3://${aws_s3_bucket.tables.bucket}"
      SCANS_RAW           = "s3://${local.raw_bucket}/${local.raw_prefix}"
      SCANS_OPENFOODFACTS = "hf"
      SCANS_FILES         = "s3://${aws_s3_bucket.tables.bucket}/files/"
      SCANS_SITE          = "s3://${aws_s3_bucket.site.bucket}"
      # Copied once from Snacker's prod working bucket by hand (README.md), never by Terraform.
      SCANS_ARCHIVE = "s3://${aws_s3_bucket.tables.bucket}/snacker-archive.csv"
    })
  }

  lifecycle {
    precondition {
      condition     = var.image_uri != ""
      error_message = "Set image_uri (<repository URL>@<digest>); apply only aws_ecr_repository.scans without it."
    }
  }

  depends_on = [aws_cloudwatch_log_group.function, aws_iam_role_policy_attachment.function_logs]
}

# The state machine and its role, which may only invoke the graph's functions.
data "aws_iam_policy_document" "states_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "state_machine" {
  name               = "${local.prefix}-state-machine"
  assume_role_policy = data.aws_iam_policy_document.states_trust.json
}

data "aws_iam_policy_document" "invoke" {
  statement {
    actions = ["lambda:InvokeFunction"]
    resources = flatten([
      for f in aws_lambda_function.function : [f.arn, "${f.arn}:*"]
    ])
  }
}

resource "aws_iam_role_policy" "state_machine_invoke" {
  name   = "invoke"
  role   = aws_iam_role.state_machine.id
  policy = data.aws_iam_policy_document.invoke.json
}

resource "aws_sfn_state_machine" "scans" {
  name     = local.prefix
  type     = "STANDARD"
  role_arn = aws_iam_role.state_machine.arn
  definition = replace(
    jsonencode(local.manifest.state_machine),
    "$${function_prefix}",
    local.function_prefix,
  )

  depends_on = [aws_iam_role_policy.state_machine_invoke, aws_lambda_function.function]
}

# Snacker's schedule (parity ticket 09): every 30 minutes, and a daily OpenFoodFacts download.
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.scans.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "start-execution"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

locals {
  schedules = {
    every-30-minutes = { expression = "rate(30 minutes)", input = {} }
    daily-download   = { expression = "cron(0 3 * * ? *)", input = { download = true } }
  }
}

resource "aws_scheduler_schedule" "scans" {
  for_each                     = local.schedules
  name                         = "${local.prefix}-${each.key}"
  schedule_expression          = each.value.expression
  schedule_expression_timezone = "Asia/Bangkok"
  state                        = var.schedules_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.scans.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode(each.value.input)

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}

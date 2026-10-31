# The stepdag graph (#117, #121): Snacker's build as one function per asset in a Step Functions
# workflow. Everything per asset comes from graph.manifest.json (`stepdag manifest
# snacker.graph.definitions:defs`, from backend/): nothing here names an asset. The functions run
# the one image, as the legacy build's do; the admin configuration creates their roles.
#
# Until the switchover it publishes to the environment's shadow bucket, and its parity asset diffs
# that with the legacy build's write_data on the same inputs (#122, #123).

locals {
  graph_manifest        = jsondecode(file("${path.module}/graph.manifest.json"))
  graph_function_prefix = "${local.prefix}-graph-"
  graph_functions       = var.graph_enabled ? local.graph_manifest.functions : {}
  graph_site_bucket     = var.graph_publishes_to == "real" ? local.site_bucket : "${local.prefix}-shadow"

  graph_settings = {
    SCANS_RAW = "s3://${var.graph_raw_bucket}/raw/data/scanner/"
    # The Delta tables, and the JSON pointers under tables/json/.
    SCANS_TABLES        = "s3://${local.working_bucket}/tables"
    SCANS_FILES         = "s3://${local.working_bucket}/files/"
    SCANS_OPENFOODFACTS = "hf"
    SCANS_ARCHIVE       = "s3://${local.working_bucket}/snacker-archive.csv"
    SCANS_SITE          = "s3://${local.graph_site_bucket}"
  }

  graph_schedules = var.graph_enabled ? {
    every-30-minutes = { expression = "rate(30 minutes)", input = {} }
    daily-download   = { expression = "cron(0 3 * * ? *)", input = { download = true } }
  } : {}
}

resource "aws_cloudwatch_log_group" "graph" {
  for_each          = local.graph_functions
  name              = "/aws/lambda/${local.graph_function_prefix}${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "graph" {
  for_each = local.graph_functions

  function_name = "${local.graph_function_prefix}${each.key}"
  role          = var.graph_role_arns[each.value.role]
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  memory_size   = each.value.memory
  timeout       = each.value.timeout

  image_config {
    command = [each.value.handler]
  }

  ephemeral_storage {
    size = each.value.ephemeral_storage
  }

  environment {
    variables = merge(each.value.environment, local.graph_settings)
  }

  depends_on = [aws_cloudwatch_log_group.graph]
}

resource "aws_sfn_state_machine" "graph" {
  count    = var.graph_enabled ? 1 : 0
  name     = "${local.prefix}-graph"
  type     = "STANDARD"
  role_arn = var.graph_state_machine_role_arn
  definition = replace(
    jsonencode(local.graph_manifest.state_machine),
    "$${function_prefix}",
    local.graph_function_prefix,
  )

  depends_on = [aws_lambda_function.graph]
}

# Snacker's schedule: every 30 minutes, and a daily OpenFoodFacts download at 03:00 in Bangkok.
# Toggle them only here (graph_schedules_enabled): a change made in the console is undone by the
# next apply.
resource "aws_scheduler_schedule" "graph" {
  for_each                     = local.graph_schedules
  name                         = "${local.prefix}-graph-${each.key}"
  schedule_expression          = each.value.expression
  schedule_expression_timezone = "Asia/Bangkok"
  state                        = var.graph_schedules_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.graph[0].arn
    role_arn = var.scheduler_role_arn
    input    = jsonencode(each.value.input)

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}

# OpenFoodFacts copies are 8 GB each and named by revision; a reader only ever needs a recent one.
# A failed copy's multipart upload is aborted by boto3, and expired here if the function died first.
resource "aws_s3_bucket_lifecycle_configuration" "working" {
  count  = var.graph_enabled ? 1 : 0
  bucket = aws_s3_bucket.working.id

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

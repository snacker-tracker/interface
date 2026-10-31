# The stepdag graph (#117, #121): the roles its functions and state machine run as, and the
# shadow site it publishes to until the switchover. The main configuration creates the graph from
# the manifest (`infra/main/graph.manifest.json`) and only passes these roles.

locals {
  graph_manifest      = jsondecode(file("${path.module}/../main/graph.manifest.json"))
  graph_functions     = "${local.function_arn}:${local.prefix}-graph-*"
  graph_state_machine = "arn:aws:states:${var.region}:${local.account}:stateMachine:${local.prefix}-graph"
  shadow_bucket       = "${local.prefix}-shadow"
  shadow_bucket_arn   = "arn:aws:s3:::${local.shadow_bucket}"
  graph_raw_prefix    = "raw/data/scanner/"
  tables_prefix       = "tables/"
  files_prefix        = "files/"
}

# --- The shadow site: the graph's data/ tree, beside the legacy build's real one ---

resource "aws_s3_bucket" "shadow" {
  bucket = local.shadow_bucket
}

resource "aws_s3_bucket_public_access_block" "shadow" {
  bucket                  = aws_s3_bucket.shadow.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "shadow" {
  bucket = aws_s3_bucket.shadow.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# SSE-S3, as the site bucket: publishing compares each file's MD5 with the object's ETag (ADR 0004).
resource "aws_s3_bucket_server_side_encryption_configuration" "shadow" {
  bucket = aws_s3_bucket.shadow.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# --- The functions: one role per manifest role, snacker-tracker-<env>-graph-<role> ---

resource "aws_iam_role" "graph" {
  for_each           = toset(local.graph_manifest.roles)
  name               = "${local.prefix}-graph-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy" "graph" {
  for_each = aws_iam_role.graph
  role     = each.value.id
  name     = "graph"
  policy   = data.aws_iam_policy_document.graph.json
}

data "aws_iam_policy_document" "graph" {
  # Read-only, and only the raw events: in dev too, the graph reads prod's (#121).
  statement {
    sid       = "ReadRawEvents"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.graph_raw_bucket}/${local.graph_raw_prefix}*"]
  }

  statement {
    sid       = "ListRawEvents"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.graph_raw_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.graph_raw_prefix}*"]
    }
  }

  # The Delta tables and the JSON pointers beside them (tables/), and the OpenFoodFacts copies
  # (files/). The archive is listed to tell it from a prefix, as the build's fetch does.
  statement {
    sid       = "ListTablesFilesAndArchive"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.working_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.tables_prefix}*", "${local.files_prefix}*", "${local.archive_key}*"]
    }
  }

  # AbortMultipartUpload: a failed OpenFoodFacts copy cleans up its upload.
  statement {
    sid       = "TablesAndFiles"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["arn:aws:s3:::${local.working_bucket}/${local.tables_prefix}*", "arn:aws:s3:::${local.working_bucket}/${local.files_prefix}*"]
  }

  statement {
    sid       = "ReadArchive"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.working_bucket}/${local.archive_key}"]
  }

  statement {
    sid       = "ListShadowData"
    actions   = ["s3:ListBucket"]
    resources = [local.shadow_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["data/*"]
    }
  }

  statement {
    sid       = "PublishShadowData"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.shadow_bucket_arn}/data/*"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arn}/${local.prefix}-graph-*:*"]
  }
}

# --- The state machine: invokes the graph's functions, nothing else ---

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
      values   = [local.account]
    }
  }
}

resource "aws_iam_role" "graph_state_machine" {
  name               = "${local.prefix}-graph-state-machine"
  assume_role_policy = data.aws_iam_policy_document.states_trust.json
}

resource "aws_iam_role_policy" "graph_state_machine" {
  role   = aws_iam_role.graph_state_machine.id
  name   = "invoke"
  policy = data.aws_iam_policy_document.graph_state_machine.json
}

data "aws_iam_policy_document" "graph_state_machine" {
  statement {
    sid       = "InvokeGraphFunctions"
    actions   = ["lambda:InvokeFunction"]
    resources = [local.graph_functions, "${local.graph_functions}:*"]
  }
}

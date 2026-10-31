# The hello graph on Step Functions (stepdag ticket 08). Everything per asset comes from
# manifest.json (`stepdag manifest hello:defs`): nothing here names an asset.

locals {
  env             = terraform.workspace
  prefix          = "stepdag-hello-${local.env}"
  function_prefix = "${local.prefix}-"
  manifest        = jsondecode(file("${path.module}/manifest.json"))
  # Built by package.py: stepdag and hello.py, run by every function.
  package = "${path.module}/build/hello.zip"
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

# The graph's values. Private by S3's defaults; a toy, so it can be destroyed with its contents.
resource "aws_s3_bucket" "values" {
  bucket        = "${local.prefix}-values"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "values" {
  bucket                  = aws_s3_bucket.values.id
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

data "aws_iam_policy_document" "values" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.values.arn]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.values.arn}/*"]
  }
}

resource "aws_iam_role_policy" "function_values" {
  for_each = aws_iam_role.function
  name     = "values"
  role     = each.value.id
  policy   = data.aws_iam_policy_document.values.json
}

resource "aws_cloudwatch_log_group" "function" {
  for_each          = local.manifest.functions
  name              = "/aws/lambda/${local.function_prefix}${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "function" {
  for_each = local.manifest.functions

  function_name    = "${local.function_prefix}${each.key}"
  package_type     = "Zip"
  filename         = local.package
  source_code_hash = filebase64sha256(local.package)
  runtime          = "python3.14"
  handler          = each.value.handler
  role             = aws_iam_role.function[each.value.role].arn
  memory_size      = each.value.memory
  timeout          = each.value.timeout
  architectures    = ["x86_64"]

  ephemeral_storage {
    size = each.value.ephemeral_storage
  }

  environment {
    variables = merge(each.value.environment, { STEPDAG_BUCKET = aws_s3_bucket.values.bucket })
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

resource "aws_sfn_state_machine" "hello" {
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

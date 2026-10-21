# The roles the functions and the schedule run as. The main configuration only passes them.

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

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
      values   = [local.account]
    }
  }
}

# --- Build: raw events in, data/ in the site bucket out ---

resource "aws_iam_role" "build" {
  name               = "${local.prefix}-build"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy" "build" {
  role   = aws_iam_role.build.id
  name   = "build"
  policy = data.aws_iam_policy_document.build.json
}

data "aws_iam_policy_document" "build" {
  statement {
    sid       = "ReadRawEvents"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = ["arn:aws:s3:::${var.raw_bucket}", "arn:aws:s3:::${var.raw_bucket}/*"]
  }

  # fetch lists the key to tell an object from a prefix, and without ListBucket a missing
  # key reads as 403, not 404.
  statement {
    sid       = "FindProducts"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.working_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.products_key}*"]
    }
  }

  statement {
    sid       = "ReadProducts"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.working_bucket}/${local.products_key}"]
  }

  statement {
    sid       = "ListData"
    actions   = ["s3:ListBucket"]
    resources = [local.site_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["data/*"]
    }
  }

  statement {
    sid       = "PublishData"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.site_bucket_arn}/data/*"]
  }

  statement {
    sid       = "StartExtraction"
    actions   = ["lambda:InvokeFunction"]
    resources = ["${local.function_arn}:${local.extract_function}"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arn}/${local.build_function}:*"]
  }
}

# --- Extraction: OpenFoodFacts (Hugging Face) and the archive in, the products table out ---

resource "aws_iam_role" "extraction" {
  name               = "${local.prefix}-extraction"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy" "extraction" {
  role   = aws_iam_role.extraction.id
  name   = "extraction"
  policy = data.aws_iam_policy_document.extraction.json
}

data "aws_iam_policy_document" "extraction" {
  # The scanned codes come from the raw scans, as with `snacker extract-products --raw`.
  statement {
    sid       = "ReadRawEvents"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = ["arn:aws:s3:::${var.raw_bucket}", "arn:aws:s3:::${var.raw_bucket}/*"]
  }

  # fetch lists the key to tell an object from a prefix, and without ListBucket a missing
  # key reads as 403, not 404.
  statement {
    sid       = "FindArchiveAndProducts"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.working_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.archive_key}*", "${local.products_key}*"]
    }
  }

  statement {
    sid       = "ReadArchive"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.working_bucket}/${local.archive_key}"]
  }

  # Read too: a table that already covers every scanned code isn't extracted again.
  statement {
    sid       = "WriteProducts"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${local.working_bucket}/${local.products_key}"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arn}/${local.extract_function}:*"]
  }
}

# --- Scheduler: starts the build ---

resource "aws_iam_role" "scheduler" {
  name               = "${local.prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "scheduler" {
  role   = aws_iam_role.scheduler.id
  name   = "scheduler"
  policy = data.aws_iam_policy_document.scheduler.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid       = "StartBuild"
    actions   = ["lambda:InvokeFunction"]
    resources = ["${local.function_arn}:${local.build_function}", "${local.function_arn}:${local.build_function}:*"]
  }
}

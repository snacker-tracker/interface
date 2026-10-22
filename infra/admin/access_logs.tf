# Where the distribution's access logs land (ADR 0010): a private bucket for the archive, and the
# permission for CloudWatch log delivery to write into the main configuration's log group. Both
# are resource policies, so they're created here, ahead of the deliveries CI creates.

resource "aws_s3_bucket" "access_logs" {
  bucket = local.access_logs_bucket
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# SSE-S3: log delivery can't use an AWS managed KMS key, and a customer managed one isn't worth it here.
resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Logs carry client IPs, so they don't outlive their purpose (ADR 0010).
resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    id     = "expire"
    status = "Enabled"
    filter {}
    expiration {
      days = var.access_log_retention_days
    }
  }
}

resource "aws_s3_bucket_policy" "access_logs" {
  bucket     = aws_s3_bucket.access_logs.id
  policy     = data.aws_iam_policy_document.access_logs_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.access_logs]
}

# The statements CloudWatch log delivery would add itself, given s3:PutBucketPolicy, which CI may
# not have. Only this environment's delivery sources may write, and only under cloudfront/.
data "aws_iam_policy_document" "access_logs_bucket" {
  statement {
    sid       = "AWSLogDeliveryWrite"
    actions   = ["s3:PutObject"]
    resources = ["${local.access_logs_bucket_arn}/${local.access_logs_s3_prefix}/*"]
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.log_delivery_arn}:delivery-source:${local.prefix}-*"]
    }
  }

  # Delivery checks the bucket first; without these it still works, but CloudTrail fills with AccessDenied.
  statement {
    sid       = "AWSLogDeliveryAclCheck"
    actions   = ["s3:GetBucketAcl", "s3:ListBucket"]
    resources = [local.access_logs_bucket_arn]
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.log_delivery_arn}:delivery-source:${local.prefix}-*"]
    }
  }
}

# CloudFront's delivery source lives in us-east-1, and so must a CloudWatch Logs destination.
# An account-level policy over the /aws/vendedlogs/ prefix means delivery never needs
# logs:PutResourcePolicy, which CI may not have.
resource "aws_cloudwatch_log_resource_policy" "access_log_delivery" {
  region          = "us-east-1"
  policy_name     = "${local.prefix}-access-log-delivery"
  policy_document = data.aws_iam_policy_document.access_log_delivery.json
}

data "aws_iam_policy_document" "access_log_delivery" {
  statement {
    sid       = "AWSLogDeliveryWrite"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.access_log_group_arn}:log-stream:*"]
    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.log_delivery_arn}:*"]
    }
  }
}

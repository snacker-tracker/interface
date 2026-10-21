# The site bucket stays private: account-wide Block Public Access is on, so CloudFront reads it
# through Origin Access Control. The distribution is the main configuration's, so the policy
# admits CloudFront from this account rather than one distribution ARN.

resource "aws_s3_bucket" "site" {
  bucket = local.site_bucket
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# SSE-S3, not KMS: publishing compares each file's MD5 with the object's ETag (ADR 0004).
resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket     = aws_s3_bucket.site.id
  policy     = data.aws_iam_policy_document.site_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.site]
}

data "aws_iam_policy_document" "site_bucket" {
  statement {
    sid       = "CloudFrontReads"
    actions   = ["s3:GetObject"]
    resources = ["${local.site_bucket_arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [local.account]
    }
  }

  # Without ListBucket a missing key reads as 403, not 404; the distribution maps both to index.html.
  statement {
    sid       = "CloudFrontLists"
    actions   = ["s3:ListBucket"]
    resources = [local.site_bucket_arn]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [local.account]
    }
  }
}

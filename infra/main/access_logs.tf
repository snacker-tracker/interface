# The distribution's access logs (ADR 0010): one standard logging (v2) delivery source feeding a
# CloudWatch log group, for Logs Insights queries, and the access-log bucket (infra/admin), for the
# archive. Log delivery for CloudFront is set up in us-east-1, and the log group has to be there too.

locals {
  access_logs_bucket = "${local.prefix}-access-logs"

  # Client IP is kept for security and operations; user agent, X-Forwarded-For, cookies and
  # referrer aren't logged at all (ADR 0010).
  access_log_fields = [
    "date", "time", "x-edge-location", "c-ip", "c-country", "asn",
    "cs-method", "x-host-header", "cs-uri-stem", "cs-uri-query", "sc-status",
    "sc-bytes", "cs-bytes", "time-taken", "x-edge-result-type", "cache-behavior-path-pattern",
  ]
}

# Under /aws/vendedlogs/, which the admin configuration's resource policy lets log delivery write to.
resource "aws_cloudwatch_log_group" "access_logs" {
  provider          = aws.us_east_1
  name              = "/aws/vendedlogs/cloudfront/${local.prefix}-site"
  retention_in_days = var.access_log_retention_days
}

resource "aws_cloudwatch_log_delivery_source" "site" {
  provider     = aws.us_east_1
  name         = "${local.prefix}-site"
  log_type     = "ACCESS_LOGS"
  resource_arn = aws_cloudfront_distribution.site.arn
}

resource "aws_cloudwatch_log_delivery_destination" "access_log_group" {
  provider      = aws.us_east_1
  name          = "${local.prefix}-site-log-group"
  output_format = "json"

  delivery_destination_configuration {
    destination_resource_arn = aws_cloudwatch_log_group.access_logs.arn
  }
}

# For CloudFront the prefix replaces the default AWSLogs/<account>/CloudFront/ path. The bucket's
# policy only admits writes under it.
resource "aws_cloudwatch_log_delivery_destination" "access_logs_bucket" {
  provider      = aws.us_east_1
  name          = "${local.prefix}-site-bucket"
  output_format = "json"

  delivery_destination_configuration {
    destination_resource_arn = "arn:aws:s3:::${local.access_logs_bucket}/cloudfront"
  }
}

resource "aws_cloudwatch_log_delivery" "access_log_group" {
  provider                 = aws.us_east_1
  delivery_source_name     = aws_cloudwatch_log_delivery_source.site.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.access_log_group.arn
  record_fields            = local.access_log_fields
}

# Hive-compatible, hour-partitioned keys (distributionid=…/year=…/month=…/day=…/hour=…), so a query
# engine can be pointed at the bucket later. Glue wants the lowercase distribution variable.
resource "aws_cloudwatch_log_delivery" "access_logs_bucket" {
  provider                 = aws.us_east_1
  delivery_source_name     = aws_cloudwatch_log_delivery_source.site.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.access_logs_bucket.arn
  record_fields            = local.access_log_fields

  s3_delivery_configuration {
    enable_hive_compatible_path = true
    suffix_path                 = "{distributionid}/{yyyy}/{MM}/{dd}/{HH}"
  }

  # Created after the log group's delivery rather than alongside it, so the source is never
  # changed by two calls at once.
  depends_on = [aws_cloudwatch_log_delivery.access_log_group]
}

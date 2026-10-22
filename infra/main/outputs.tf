output "site_url" {
  value = "https://${var.hostnames[0]}"
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "working_bucket" {
  value = aws_s3_bucket.working.bucket
}

output "site_bucket" {
  value = local.site_bucket
}

output "build_function" {
  value = aws_lambda_function.build.function_name
}

output "extract_function" {
  value = aws_lambda_function.extract.function_name
}

output "distribution_domain" {
  description = "The distribution's own cloudfront.net name, to check before the hostnames point at it."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "access_log_group" {
  description = "Query it with Logs Insights in us-east-1."
  value       = aws_cloudwatch_log_group.access_logs.name
}

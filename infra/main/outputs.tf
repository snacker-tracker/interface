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

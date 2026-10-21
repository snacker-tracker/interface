output "site_url" {
  value = "https://${var.hostnames[0]}"
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "working_bucket" {
  value = aws_s3_bucket.working.bucket
}

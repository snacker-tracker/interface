output "build_role_arn" {
  value = aws_iam_role.build.arn
}

output "extraction_role_arn" {
  value = aws_iam_role.extraction.arn
}

output "scheduler_role_arn" {
  value = aws_iam_role.scheduler.arn
}

output "site_bucket" {
  value = aws_s3_bucket.site.bucket
}

output "access_logs_bucket" {
  value = aws_s3_bucket.access_logs.bucket
}

output "working_bucket" {
  description = "Not created here: the name the main configuration must give it, which the roles are written against."
  value       = local.working_bucket
}

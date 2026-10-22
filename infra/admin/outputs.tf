output "ci_role_arn" {
  value = aws_iam_role.ci.arn
}

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

output "ecr_repository_url" {
  value = "${local.account}.dkr.ecr.${var.region}.amazonaws.com/${var.ecr_repository_name}"
}

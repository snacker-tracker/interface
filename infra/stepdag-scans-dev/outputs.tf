output "tables_bucket" {
  value = aws_s3_bucket.tables.bucket
}

output "repository_url" {
  value = aws_ecr_repository.scans.repository_url
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.scans.arn
}

output "site_bucket" {
  value = aws_s3_bucket.site.bucket
}

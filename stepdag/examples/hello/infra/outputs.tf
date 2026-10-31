output "bucket" {
  value = aws_s3_bucket.values.bucket
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.hello.arn
}

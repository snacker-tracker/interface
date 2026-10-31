# Both functions run one image by digest (ADR 0006); the handler picks the job.

resource "aws_cloudwatch_log_group" "build" {
  name              = "/aws/lambda/${local.build_function}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "extract" {
  name              = "/aws/lambda/${local.extract_function}"
  retention_in_days = var.log_retention_days
}

# No reserved concurrency of 1 yet: the account's limit is 10, all of which AWS keeps unreserved.
# A build takes under a minute every 15, and publishing corrects itself (ADR 0004).
# Peaks around 680 MB; CPU grows with memory, so a smaller size also means a slower build.
resource "aws_lambda_function" "build" {
  function_name = local.build_function
  role          = var.build_role_arn
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  memory_size   = 768
  timeout       = 900

  environment {
    variables = local.settings
  }

  depends_on = [aws_cloudwatch_log_group.build]
}

# About 3 minutes and 1.4 GB at peak (aws-deployment ticket 03); CPU grows with memory.
resource "aws_lambda_function" "extract" {
  function_name = local.extract_function
  role          = var.extraction_role_arn
  package_type  = "Image"
  image_uri     = var.image_uri
  architectures = ["x86_64"]
  memory_size   = 3008
  timeout       = 900

  image_config {
    command = ["snacker.handlers.extract_handler"]
  }

  environment {
    variables = local.settings
  }

  depends_on = [aws_cloudwatch_log_group.extract]
}

# The build starts extractions asynchronously; a failed one is retried by the next build that
# still finds codes missing, so Lambda's own retries would only repeat a 3-minute scan.
resource "aws_lambda_function_event_invoke_config" "extract" {
  function_name          = aws_lambda_function.extract.function_name
  maximum_retry_attempts = 0
}

# Off once the stepdag graph publishes the site (#124): the function stays, so turning this back
# on is the rollback.
resource "aws_scheduler_schedule" "build" {
  name                = local.build_function
  schedule_expression = var.build_schedule
  state               = var.build_schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.build.arn
    role_arn = var.scheduler_role_arn

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}

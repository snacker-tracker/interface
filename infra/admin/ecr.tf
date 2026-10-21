# The shared image repository (ADR 0006) lives here only until it moves to the repo that
# manages shared infrastructure. Only the dev workspace creates it; prod refers to it by name.

resource "aws_ecr_repository" "backend" {
  count                = local.env == "dev" ? 1 : 0
  name                 = var.ecr_repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Lambda pulls the image as itself. Granting it here means the CI roles never need
# ecr:SetRepositoryPolicy, which Lambda otherwise asks of whoever creates the function.
resource "aws_ecr_repository_policy" "backend" {
  count      = local.env == "dev" ? 1 : 0
  repository = aws_ecr_repository.backend[0].name
  policy     = data.aws_iam_policy_document.ecr_lambda_pull.json
}

data "aws_iam_policy_document" "ecr_lambda_pull" {
  statement {
    sid     = "LambdaPulls"
    actions = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.function_arn}:snacker-tracker-*"]
    }
  }
}

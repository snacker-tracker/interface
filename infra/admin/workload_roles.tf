# The trust policies of the roles the graph's functions and schedules run as, and the scheduler's
# role. The main configuration only passes them.

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

# --- Scheduler: starts the graph ---

resource "aws_iam_role" "scheduler" {
  name               = "${local.prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "scheduler" {
  role   = aws_iam_role.scheduler.id
  name   = "scheduler"
  policy = data.aws_iam_policy_document.scheduler.json
}

data "aws_iam_policy_document" "scheduler" {
  # The graph's schedules (graph.tf, #121).
  statement {
    sid       = "StartGraph"
    actions   = ["states:StartExecution"]
    resources = [local.graph_state_machine]
  }
}

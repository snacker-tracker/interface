# The role the main configuration is applied with (ADR 0005). It manages only resources named
# snacker-tracker-<env>-*, or tagged project=snacker-tracker where AWS generates the ID, and on
# IAM it can only read and pass its environment's workload roles. It never writes a permission.

locals {
  raw_buckets = ["snacker-tracker-dev", "snacker-tracker-prod"]
  workload_roles = {
    lambda    = ["${local.role_arn}/${local.prefix}-build", "${local.role_arn}/${local.prefix}-extraction"]
    scheduler = ["${local.role_arn}/${local.prefix}-scheduler"]
  }
  project_tag = { variable = "project", value = "snacker-tracker" }
}

data "aws_iam_policy_document" "ci_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Deploys run in the matching GitHub environment; pull requests only plan.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:environment:${local.env}",
        "repo:${var.github_repo}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "ci" {
  name               = "${local.prefix}-ci"
  assume_role_policy = data.aws_iam_policy_document.ci_trust.json
}

resource "aws_iam_policy" "ci" {
  for_each = {
    workloads = data.aws_iam_policy_document.ci_workloads.json
    edge      = data.aws_iam_policy_document.ci_edge.json
    guards    = data.aws_iam_policy_document.ci_guards.json
  }
  name   = "${local.prefix}-ci-${each.key}"
  policy = each.value
}

resource "aws_iam_role_policy_attachment" "ci" {
  for_each   = aws_iam_policy.ci
  role       = aws_iam_role.ci.name
  policy_arn = each.value.arn
}

# --- Functions, schedule, logs, the working bucket, the site's frontend files, the image ---

data "aws_iam_policy_document" "ci_workloads" {
  # No AddPermission or function URLs: those are resource policies, and nothing needs them.
  statement {
    sid = "Functions"
    actions = [
      "lambda:Get*", "lambda:List*",
      "lambda:CreateFunction", "lambda:DeleteFunction", "lambda:PublishVersion",
      "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration",
      "lambda:PutFunctionConcurrency", "lambda:DeleteFunctionConcurrency",
      "lambda:PutFunctionEventInvokeConfig", "lambda:UpdateFunctionEventInvokeConfig",
      "lambda:DeleteFunctionEventInvokeConfig",
      "lambda:TagResource", "lambda:UntagResource", "lambda:InvokeFunction",
    ]
    resources = ["${local.function_arn}:${local.prefix}-*"]
  }

  statement {
    sid       = "ListFunctions"
    actions   = ["lambda:ListFunctions", "scheduler:ListSchedules", "logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid = "Schedule"
    actions = [
      "scheduler:GetSchedule", "scheduler:CreateSchedule",
      "scheduler:UpdateSchedule", "scheduler:DeleteSchedule",
    ]
    resources = ["arn:aws:scheduler:${var.region}:${local.account}:schedule/default/${local.prefix}-*"]
  }

  statement {
    sid = "LogGroups"
    actions = [
      "logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy", "logs:TagResource", "logs:UntagResource",
      "logs:ListTagsForResource", "logs:TagLogGroup", "logs:ListTagsLogGroup",
    ]
    resources = ["${local.log_group_arn}/${local.prefix}-*"]
  }

  # Bucket and object policies, ACLs and public access are denied in ci_guards.
  statement {
    sid       = "WorkingBucket"
    actions   = ["s3:*"]
    resources = ["arn:aws:s3:::${local.working_bucket}", "arn:aws:s3:::${local.working_bucket}/*"]
  }

  statement {
    sid       = "ReadSiteBucket"
    actions   = ["s3:ListBucket", "s3:GetBucket*", "s3:GetEncryptionConfiguration"]
    resources = [local.site_bucket_arn]
  }

  # data/* is the build's alone (ADR 0004); the deny is in ci_guards.
  statement {
    sid       = "FrontendFiles"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.site_bucket_arn}/*"]
  }

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "Image"
    actions = concat(
      [
        "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability",
        "ecr:DescribeImages", "ecr:DescribeRepositories",
      ],
      var.can_push_images ? [
        "ecr:PutImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
      ] : [],
    )
    resources = [local.ecr_repository]
  }
}

# --- CloudFront, its certificate and DNS records ---

data "aws_iam_policy_document" "ci_edge" {
  # Creates take no resource ARN (the ID doesn't exist yet), only "*"; the tag scopes them.
  statement {
    sid       = "CreateTaggedDistributions"
    actions   = ["cloudfront:CreateDistribution", "cloudfront:TagResource"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/${local.project_tag.variable}"
      values   = [local.project_tag.value]
    }
  }

  statement {
    sid = "ManageTaggedDistributions"
    actions = [
      "cloudfront:GetDistribution", "cloudfront:GetDistributionConfig",
      "cloudfront:UpdateDistribution", "cloudfront:DeleteDistribution",
      "cloudfront:ListTagsForResource", "cloudfront:UntagResource",
      "cloudfront:CreateInvalidation", "cloudfront:GetInvalidation",
    ]
    resources = ["arn:aws:cloudfront::${local.account}:distribution/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/${local.project_tag.variable}"
      values   = [local.project_tag.value]
    }
  }

  # Origin access controls can't carry tags. They grant nothing by themselves: the site
  # bucket's policy decides what CloudFront may read.
  statement {
    sid       = "CreateOriginAccessControls"
    actions   = ["cloudfront:CreateOriginAccessControl"]
    resources = ["*"]
  }

  statement {
    sid = "OriginAccessControls"
    actions = [
      "cloudfront:GetOriginAccessControl", "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
    ]
    resources = ["arn:aws:cloudfront::${local.account}:origin-access-control/*"]
  }

  statement {
    sid = "ReadCloudFront"
    actions = [
      "cloudfront:ListDistributions", "cloudfront:ListOriginAccessControls",
      "cloudfront:GetCachePolicy", "cloudfront:ListCachePolicies",
      "cloudfront:GetOriginRequestPolicy", "cloudfront:ListOriginRequestPolicies",
      "cloudfront:GetResponseHeadersPolicy", "cloudfront:ListResponseHeadersPolicies",
      "acm:ListCertificates",
    ]
    resources = ["*"]
  }

  # CloudFront certificates live in us-east-1. Requests take no resource ARN, only "*".
  statement {
    sid       = "RequestTaggedCertificates"
    actions   = ["acm:RequestCertificate", "acm:AddTagsToCertificate"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestTag/${local.project_tag.variable}"
      values   = [local.project_tag.value]
    }
  }

  statement {
    sid = "ManageTaggedCertificates"
    actions = [
      "acm:DescribeCertificate", "acm:GetCertificate", "acm:DeleteCertificate",
      "acm:ListTagsForCertificate", "acm:RemoveTagsFromCertificate",
    ]
    resources = ["arn:aws:acm:us-east-1:${local.account}:certificate/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/${local.project_tag.variable}"
      values   = [local.project_tag.value]
    }
  }

  statement {
    sid       = "ReadZone"
    actions   = ["route53:GetHostedZone", "route53:ListResourceRecordSets", "route53:ListTagsForResource"]
    resources = ["arn:aws:route53:::hostedzone/${var.hosted_zone_id}"]
  }

  statement {
    sid       = "FindZoneAndChanges"
    actions   = ["route53:ListHostedZones", "route53:ListHostedZonesByName", "route53:GetChange"]
    resources = ["*"]
  }

  # Only this environment's names and their ACM validation records (_<token>.<name>).
  statement {
    sid       = "OwnRecords"
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = ["arn:aws:route53:::hostedzone/${var.hosted_zone_id}"]
    condition {
      test     = "ForAllValues:StringLike"
      variable = "route53:ChangeResourceRecordSetsNormalizedRecordNames"
      values   = flatten([for name in var.hostnames : [name, "_*.${name}"]])
    }
  }
}

# --- Terraform state, IAM, and the denies that hold whatever the allows above say ---

data "aws_iam_policy_document" "ci_guards" {
  # The S3 backend lists env:/ to find workspaces, which shows other configurations' key
  # names but none of their contents.
  statement {
    sid       = "ListOwnState"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.state_bucket}"]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["env:/", "${local.main_state_object}*"]
    }
  }

  statement {
    sid       = "OwnState"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${var.state_bucket}/${local.main_state_object}"]
  }

  statement {
    sid       = "OwnStateLock"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${var.state_bucket}/${local.main_state_object}.tflock"]
  }

  statement {
    sid       = "ReadWorkloadRoles"
    actions   = ["iam:GetRole"]
    resources = flatten(values(local.workload_roles))
  }

  dynamic "statement" {
    for_each = local.workload_roles
    content {
      sid       = "PassTo${title(statement.key)}"
      actions   = ["iam:PassRole"]
      resources = statement.value
      condition {
        test     = "StringEquals"
        variable = "iam:PassedToService"
        values   = ["${statement.key}.amazonaws.com"]
      }
    }
  }

  statement {
    sid       = "NotData"
    effect    = "Deny"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.site_bucket_arn}/data/*"]
  }

  statement {
    sid       = "NotRawEvents"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = flatten([for bucket in local.raw_buckets : ["arn:aws:s3:::${bucket}", "arn:aws:s3:::${bucket}/*"]])
  }

  statement {
    sid    = "NoBucketPermissions"
    effect = "Deny"
    actions = [
      "s3:PutBucketPolicy", "s3:DeleteBucketPolicy", "s3:PutBucketAcl", "s3:PutObjectAcl",
      "s3:PutBucketPublicAccessBlock", "s3:PutAccountPublicAccessBlock",
      "s3:PutBucketOwnershipControls",
    ]
    resources = ["*"]
  }

  # The project tag is what scopes CloudFront and ACM; removing it would hide a resource.
  statement {
    sid       = "KeepProjectTag"
    effect    = "Deny"
    actions   = ["cloudfront:UntagResource", "acm:RemoveTagsFromCertificate"]
    resources = ["*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "aws:TagKeys"
      values   = [local.project_tag.variable]
    }
  }
}

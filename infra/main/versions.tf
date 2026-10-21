terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Each workspace's state is at env:/<workspace>/snacker-tracker-interface, the one key the CI
  # roles can reach (infra/admin).
  backend "s3" {
    bucket       = "snacker-tracker-aws-infra-tfstate"
    key          = "snacker-tracker-interface"
    region       = "ap-southeast-1"
    use_lockfile = true
  }
}

# The organization's tag policy requires these keys, case included. The Project tag is also
# what lets the CI role manage CloudFront and ACM (ADR 0005).
locals {
  tags = {
    Project     = "snacker-tracker"
    Environment = local.env
    Component   = "interface"
    ManagedBy   = "terraform"
    Repository  = "git@github.com:snacker-tracker/interface.git"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

# CloudFront certificates live in us-east-1.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.tags
  }
}

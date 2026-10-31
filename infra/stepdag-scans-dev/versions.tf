terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Same state bucket as Snacker's configurations, its own key: each workspace's state is at
  # env:/<workspace>/stepdag-scans. Applied by hand (README.md).
  backend "s3" {
    bucket       = "snacker-tracker-aws-infra-tfstate"
    key          = "stepdag-scans"
    region       = "ap-southeast-1"
    use_lockfile = true
  }
}

locals {
  tags = {
    Project     = "snacker-tracker"
    Environment = local.env
    Component   = "stepdag-scans"
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

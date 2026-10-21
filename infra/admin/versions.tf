terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Each workspace's state is at env:/<workspace>/snacker-tracker-interface-admin. The CI
  # roles can reach only the main configuration's key, never this one.
  backend "s3" {
    bucket       = "snacker-tracker-aws-infra-tfstate"
    key          = "snacker-tracker-interface-admin"
    region       = "ap-southeast-1"
    use_lockfile = true
  }
}

# The organization's tag policy requires these keys, case included.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "snacker-tracker"
      Environment = local.env
      Component   = "interface"
      ManagedBy   = "terraform"
      Repository  = "git@github.com:snacker-tracker/interface.git"
    }
  }
}

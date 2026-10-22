variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "raw_bucket" {
  description = "The environment's raw scanner bucket (snacker-tracker-dev or -prod). It exists already and isn't managed here."
  type        = string
}

variable "hosted_zone_id" {
  description = "The khanom.xyz hosted zone."
  type        = string
  default     = "Z0781732PCOBWRVFR9YS"
}

variable "hostnames" {
  description = "The names this environment's CI role may manage in the hosted zone, with their ACM validation records."
  type        = list(string)
}

variable "github_repo" {
  # GitHub puts the owner's and repository's numeric IDs in the OIDC subject
  # (repo:<owner>@<id>/<name>@<id>:…), so a deleted and recreated repository of the same name
  # can't assume the role.
  description = "<owner>@<owner id>/<name>@<repository id> of the GitHub repository whose workflows assume the CI role."
  type        = string
  default     = "snacker-tracker@59108816/interface@1428184726"
}

variable "ecr_repository_name" {
  description = "The shared repository for the backend image (ADR 0006). Created by the dev workspace until it moves out of this repo."
  type        = string
  default     = "snacker-tracker-lambda/interface"
}

variable "can_push_images" {
  description = "Whether the CI role may push to the ECR repository: dev builds the image, prod only reads it."
  type        = bool
}

variable "state_bucket" {
  type    = string
  default = "snacker-tracker-aws-infra-tfstate"
}

variable "main_state_key" {
  description = "The main configuration's backend key; its workspace's state is at env:/<env>/<key>."
  type        = string
  default     = "snacker-tracker-interface"
}

variable "access_log_retention_days" {
  description = "How long the access-log bucket keeps CloudFront's logs (ADR 0010)."
  type        = number
  default     = 90
}

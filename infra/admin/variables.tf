variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "raw_bucket" {
  description = "The environment's raw scanner bucket (snacker-tracker-dev or -prod). It exists already and isn't managed here."
  type        = string
}

variable "ecr_repository_name" {
  description = "The shared repository for the backend image (ADR 0006). Created by the dev workspace until it moves out of this repo."
  type        = string
  default     = "snacker-tracker-lambda/interface"
}

variable "access_log_retention_days" {
  description = "How long the access-log bucket keeps CloudFront's logs (ADR 0010)."
  type        = number
  default     = 90
}

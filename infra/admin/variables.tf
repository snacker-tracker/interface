variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "raw_bucket" {
  description = "The environment's raw scanner bucket (snacker-tracker-dev or -prod). It exists already and isn't managed here."
  type        = string
}

variable "access_log_retention_days" {
  description = "How long the access-log bucket keeps CloudFront's logs (ADR 0010)."
  type        = number
  default     = 90
}

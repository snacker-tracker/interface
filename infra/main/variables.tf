variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "image_uri" {
  description = "The backend image by digest: <repository url>@sha256:… (ADR 0006)."
  type        = string
}

variable "build_role_arn" {
  description = "From the admin configuration's outputs."
  type        = string
}

variable "extraction_role_arn" {
  description = "From the admin configuration's outputs."
  type        = string
}

variable "scheduler_role_arn" {
  description = "From the admin configuration's outputs."
  type        = string
}

variable "raw_bucket" {
  description = "The environment's raw scanner bucket, read-only and not managed here."
  type        = string
}

variable "hostnames" {
  description = "The names the site is served on; the first is the certificate's main name."
  type        = list(string)
}

variable "serve_hostnames" {
  description = "Whether the hostnames' A/AAAA records point at the distribution. The certificate and its validation records exist either way."
  type        = bool
  default     = true
}

variable "hosted_zone_id" {
  type    = string
  default = "Z0781732PCOBWRVFR9YS"
}

variable "build_schedule" {
  type    = string
  default = "rate(15 minutes)"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "access_log_retention_days" {
  description = "How long the CloudWatch log group keeps CloudFront's access logs (ADR 0010); the bucket keeps them longer."
  type        = number
  default     = 30
}

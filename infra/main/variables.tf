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

# The stepdag graph (graph.tf, #121).

variable "graph_enabled" {
  description = "Whether this environment runs the stepdag graph. Off in prod until its shadow (#123)."
  type        = bool
  default     = false
}

variable "graph_role_arns" {
  description = "The graph's function roles by manifest role, from the admin configuration's graph_role_arns output."
  type        = map(string)
  default     = {}
}

variable "graph_state_machine_role_arn" {
  description = "From the admin configuration's outputs."
  type        = string
  default     = ""
}

variable "graph_raw_bucket" {
  description = "The raw scanner bucket the graph reads, read-only. Prod's in both environments: dev's has almost no events (#121)."
  type        = string
  default     = "snacker-tracker-prod"
}

variable "graph_publishes_to" {
  description = "shadow (the environment's shadow bucket) until the switchover (#124), then real (the site bucket)."
  type        = string
  default     = "shadow"

  validation {
    condition     = contains(["shadow", "real"], var.graph_publishes_to)
    error_message = "graph_publishes_to is shadow or real."
  }
}

variable "graph_schedules_enabled" {
  description = "false keeps the graph's schedules but disables them."
  type        = bool
  default     = true
}

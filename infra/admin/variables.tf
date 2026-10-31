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

variable "graph_raw_bucket" {
  description = "The raw scanner bucket the stepdag graph reads (read-only). Prod's in both environments: dev's has almost no events, so dev parity would prove nothing there (#121)."
  type        = string
  default     = "snacker-tracker-prod"
}

variable "graph_publishes_to" {
  description = "Where the graph's functions may publish data/: shadow (the shadow bucket), or real (the site bucket) from the switchover (#124). Must match the main configuration's graph_publishes_to."
  type        = string
  default     = "shadow"

  validation {
    condition     = contains(["shadow", "real"], var.graph_publishes_to)
    error_message = "graph_publishes_to is shadow or real."
  }
}

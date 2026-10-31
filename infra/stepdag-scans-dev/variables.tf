variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

# <repository URL>@<digest>: the one image CI pushes to the shared repository (README.md).
variable "image_uri" {
  type    = string
  default = ""
}

# false keeps the schedules but disables them (Snacker's 30-minute and daily runs).
variable "schedules_enabled" {
  type    = bool
  default = true
}

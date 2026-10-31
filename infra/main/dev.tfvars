raw_bucket          = "snacker-tracker-dev"
hostnames           = ["dev.khanom.xyz"]
build_role_arn      = "arn:aws:iam::132218943709:role/snacker-tracker-dev-build"
extraction_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-extraction"
scheduler_role_arn  = "arn:aws:iam::132218943709:role/snacker-tracker-dev-scheduler"

graph_enabled                = true
graph_role_arns              = { default = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-default" }
graph_state_machine_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-state-machine"

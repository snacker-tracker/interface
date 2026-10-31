raw_bucket          = "snacker-tracker-dev"
hostnames           = ["dev.khanom.xyz"]
build_role_arn      = "arn:aws:iam::132218943709:role/snacker-tracker-dev-build"
extraction_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-extraction"
scheduler_role_arn  = "arn:aws:iam::132218943709:role/snacker-tracker-dev-scheduler"

graph_enabled                = true
graph_role_arns              = { default = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-default" }
graph_state_machine_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-state-machine"

# Off since prod's graph publishes the site (#124): dev's graph read prod's events too, so it
# proves nothing more, and the account runs only 10 functions at once.
graph_schedules_enabled = false


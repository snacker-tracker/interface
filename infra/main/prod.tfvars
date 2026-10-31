raw_bucket          = "snacker-tracker-prod"
hostnames           = ["khanom.xyz", "www.khanom.xyz"]
build_role_arn      = "arn:aws:iam::132218943709:role/snacker-tracker-prod-build"
extraction_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-prod-extraction"
scheduler_role_arn  = "arn:aws:iam::132218943709:role/snacker-tracker-prod-scheduler"

# The stepdag graph publishes the site (#124); the legacy build runs alongside until its first
# identical run, then stops (build_schedule_enabled = false).
graph_enabled                = true
graph_role_arns              = { default = "arn:aws:iam::132218943709:role/snacker-tracker-prod-graph-default" }
graph_state_machine_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-prod-graph-state-machine"
graph_publishes_to           = "real"

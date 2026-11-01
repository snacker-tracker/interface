hostnames          = ["khanom.xyz", "www.khanom.xyz"]
scheduler_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-prod-scheduler"

graph_enabled                = true
graph_role_arns              = { default = "arn:aws:iam::132218943709:role/snacker-tracker-prod-graph-default" }
graph_state_machine_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-prod-graph-state-machine"

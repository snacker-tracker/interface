hostnames          = ["dev.khanom.xyz"]
scheduler_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-scheduler"

graph_enabled                = true
graph_role_arns              = { default = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-default" }
graph_state_machine_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-dev-graph-state-machine"

# Off: dev's graph reads prod's events too, so a scheduled run would show nothing prod doesn't,
# and the account runs only 10 functions at once. Start an execution to refresh dev's site.
graph_schedules_enabled = false


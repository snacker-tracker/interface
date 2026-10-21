raw_bucket          = "snacker-tracker-prod"
hostnames           = ["khanom.xyz", "www.khanom.xyz"]
build_role_arn      = "arn:aws:iam::132218943709:role/snacker-tracker-prod-build"
extraction_role_arn = "arn:aws:iam::132218943709:role/snacker-tracker-prod-extraction"
scheduler_role_arn  = "arn:aws:iam::132218943709:role/snacker-tracker-prod-scheduler"
# Until the distribution is checked on its cloudfront.net address (ticket 08).
serve_hostnames = false

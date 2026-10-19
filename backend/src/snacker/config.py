"""Build configuration: settings that change without code changes (a new office, a longer list)."""

OFFICE_TIME_ZONES: dict[str, str] = {
    # Location prefix -> IANA time zone. The longest matching prefix wins, and a
    # scanned location with no match stops the build. Add a line per new office.
    "thailand": "Asia/Bangkok",
}

RECENT_SCANS_LIMIT = 25
"""How many of the most recent scans each list shows."""

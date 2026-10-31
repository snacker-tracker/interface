"""Build configuration: settings that change without code changes (a new office, a longer list)."""

import json
import os
from collections.abc import Mapping

OFFICE_TIME_ZONES: dict[str, str] = {
    # Location prefix -> IANA time zone. The longest matching prefix wins, and a
    # scanned location with no match stops the build. Add a line per new office.
    "thailand": "Asia/Bangkok",
}


def office_time_zones() -> Mapping[str, str]:
    """`$SCANS_OFFICE_TIME_ZONES` (JSON) if it's set, else OFFICE_TIME_ZONES. The graph's assets
    take nothing from outside but their environment, so this is how a test sets its offices."""
    configured = os.environ.get("SCANS_OFFICE_TIME_ZONES")
    return json.loads(configured) if configured else OFFICE_TIME_ZONES

RECENT_SCANS_LIMIT = 25
"""How many of the most recent scans each list shows."""

TOP_SCANS_LIMIT = 10
"""How many codes each period's top scans list shows."""

"""Reading raw EventBridge envelopes as delivered to S3."""

import json
from pathlib import Path
from typing import Any


def read_events(directory: Path) -> list[dict[str, Any]]:
    """Every JSON envelope in every file under `directory`; a file holds one envelope per line.

    A directory that doesn't exist (e.g. no heartbeats delivered yet) holds no events.
    """
    events = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events

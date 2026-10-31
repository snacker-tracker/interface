import json
from pathlib import Path

from stepdag.manifest import render

from scans_example.graph import defs

MANIFEST = Path(__file__).parent.parent / "infra" / "manifest.json"


def test_the_committed_manifest_is_up_to_date() -> None:
    fresh = render(defs, "scans_example.graph:defs")

    assert fresh == json.loads(MANIFEST.read_text()), (
        "run: uv run stepdag manifest scans_example.graph:defs > infra/manifest.json"
    )

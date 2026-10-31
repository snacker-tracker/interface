import json
from pathlib import Path

from stepdag.manifest import render

from snacker.graph.definitions import defs

MANIFEST = Path(__file__).parents[3] / "infra" / "stepdag-scans-dev" / "manifest.json"


def test_the_committed_manifest_is_up_to_date() -> None:
    fresh = render(defs, "snacker.graph.definitions:defs")

    assert fresh == json.loads(MANIFEST.read_text()), (
        "run, in backend/: uv run stepdag manifest snacker.graph.definitions:defs > ../infra/stepdag-scans-dev/manifest.json"
    )

"""The legacy build path (#117) is used only by itself, the CLI's commands for it, and the graph's
parity asset, so deleting it at the switchover (#125) touches nothing else."""

import ast
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
LEGACY = {"snacker.build", "snacker.event_cache", "snacker.extraction", "snacker.handlers"}
MAY_IMPORT_LEGACY = LEGACY | {"snacker.cli", "snacker.graph.parity"}


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(SRC).with_suffix("").parts)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_only_the_legacy_path_cli_and_parity_import_the_legacy_modules() -> None:
    importers = {
        module_name(path): sorted(imported_modules(path) & LEGACY)
        for path in SRC.rglob("*.py")
        if module_name(path) not in MAY_IMPORT_LEGACY
    }

    assert {module: legacy for module, legacy in importers.items() if legacy} == {}

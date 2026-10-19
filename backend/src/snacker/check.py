"""Checking a built output against the contract: every file matches its document's schema."""

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from snacker.schema import schema_errors


@dataclass(frozen=True)
class Violation:
    path: PurePosixPath
    """The file, relative to the data directory."""
    problem: str

    def __str__(self) -> str:
        return f"{self.path}: {self.problem}"


def document_of(path: PurePosixPath) -> str | None:
    """Which contract document a file under the data directory is, by its path; None if none."""
    match path.parts:
        case ("meta.json",):
            return "MetaFile"
        case ("locations.json",):
            return "LocationsFile"
        case ("index", "by-location", name) if name.endswith(".json"):
            return "IndexFile"
        case ("scanners", "by-location", name) if name.endswith(".json"):
            return "ScannersFile"
        case ("codes", _, "product.json"):
            return "ProductFile"
        case ("codes", _, "by-location", name) if name.endswith(".json"):
            return "CodeScansFile"
    return None


def contract_violations(data_dir: Path) -> list[Violation]:
    """Every way the files under `data_dir` break the contract, by file path."""
    violations = []
    for file in sorted(path for path in data_dir.rglob("*") if path.is_file()):
        path = PurePosixPath(file.relative_to(data_dir).as_posix())
        document = document_of(path)
        if document is None:
            violations.append(Violation(path, "not a file the contract describes"))
            continue
        try:
            content = json.loads(file.read_text())
        except json.JSONDecodeError as error:
            violations.append(Violation(path, f"not valid JSON: {error}"))
            continue
        violations += [Violation(path, error) for error in schema_errors(document, content)]
    return violations

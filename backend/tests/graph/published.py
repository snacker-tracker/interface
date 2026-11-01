"""What a local graph run published."""

from pathlib import Path


def files_under(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by path relative to it."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

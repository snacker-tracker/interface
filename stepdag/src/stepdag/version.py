"""The code version a materialization is made by, which the skip rule compares (ADR 0006)."""

import os
import subprocess


def code_version() -> str | None:
    """`$STEPDAG_CODE_VERSION` if set; otherwise the git HEAD commit of the working directory's checkout.

    None when the working tree is dirty, when git is unavailable, or outside a checkout: an asset
    stamped with None never skips.
    """
    if configured := os.environ.get("STEPDAG_CODE_VERSION"):
        return configured
    try:
        head = _git("rev-parse", "HEAD")
        dirty = _git("status", "--porcelain")
    except (OSError, subprocess.CalledProcessError):
        return None
    return None if dirty or not head else head


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

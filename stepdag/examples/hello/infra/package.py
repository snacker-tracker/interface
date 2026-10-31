"""Zips stepdag and the hello graph into the one package every hello Lambda runs.

stepdag needs only boto3, which the Lambda Python runtime provides, so the package is just source:
    uv run python infra/package.py    (from stepdag/examples/hello)
"""

import zipfile
from pathlib import Path

HELLO = Path(__file__).resolve().parent.parent
SOURCE = HELLO.parent.parent / "src"
PACKAGE = HELLO / "infra" / "build" / "hello.zip"


def main() -> None:
    PACKAGE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(PACKAGE, "w", zipfile.ZIP_DEFLATED) as package:
        for path in sorted((SOURCE / "stepdag").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                # A fixed timestamp, so an unchanged package has an unchanged hash and Terraform leaves the functions alone.
                info = zipfile.ZipInfo(path.relative_to(SOURCE).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                package.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
        info = zipfile.ZipInfo("hello.py", date_time=(2026, 1, 1, 0, 0, 0))
        package.writestr(info, (HELLO / "hello.py").read_bytes(), zipfile.ZIP_DEFLATED)
    print(PACKAGE)


if __name__ == "__main__":
    main()

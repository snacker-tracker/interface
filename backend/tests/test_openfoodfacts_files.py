"""`LocalFiles` overwriting one stable key: a reader sees the old copy or the new one, never a partial file."""

import io
from pathlib import Path

import pytest

from snacker.openfoodfacts import LocalFiles


def test_uploading_to_an_existing_key_replaces_the_whole_file(tmp_path: Path) -> None:
    files = LocalFiles(tmp_path)
    files.upload(
        "openfoodfacts/food.parquet",
        io.BytesIO(b"the old copy, longer than the new one"),
    )

    uri, size = files.upload("openfoodfacts/food.parquet", io.BytesIO(b"new"))

    assert (tmp_path / "openfoodfacts" / "food.parquet").read_bytes() == b"new"
    assert size == 3
    assert files.exists(uri)


def test_a_failed_overwrite_leaves_the_old_copy_and_no_partial_file(
    tmp_path: Path,
) -> None:
    files = LocalFiles(tmp_path)
    files.upload("openfoodfacts/food.parquet", io.BytesIO(b"the old copy"))

    class Failing(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise ConnectionResetError("the CDN went away")

    with pytest.raises(ConnectionResetError):
        files.upload("openfoodfacts/food.parquet", Failing(b"new"))

    assert (tmp_path / "openfoodfacts" / "food.parquet").read_bytes() == b"the old copy"
    assert sorted(p.name for p in (tmp_path / "openfoodfacts").iterdir()) == [
        "food.parquet"
    ]

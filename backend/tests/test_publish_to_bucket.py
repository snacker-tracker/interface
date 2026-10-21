"""Tests at the publish seam: a checked build's files in, the site bucket's data/ brought in line."""

from pathlib import Path

import pytest

from fake_bucket import FakeBucket, Put
from snacker.storage import publish_to_bucket


@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    return tmp_path / "staging"


def write_built(staging_dir: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = staging_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_every_file_goes_to_an_empty_bucket_as_short_lived_json(staging_dir: Path) -> None:
    write_built(staging_dir, {"codes/123/product.json": '{"code": "123"}\n'})
    bucket = FakeBucket()

    publish_to_bucket(staging_dir, bucket)

    assert bucket.calls == [
        Put("data/codes/123/product.json", b'{"code": "123"}\n', content_type="application/json", cache_control="max-age=60"),
    ]


def test_only_new_and_changed_files_are_uploaded(staging_dir: Path) -> None:
    write_built(staging_dir, {
        "locations.json": "same\n",
        "codes/1/product.json": "changed\n",
        "codes/2/product.json": "new\n",
    })
    bucket = FakeBucket({"data/locations.json": b"same\n", "data/codes/1/product.json": b"before\n"})

    publish_to_bucket(staging_dir, bucket)

    assert sorted(bucket.puts()) == ["data/codes/1/product.json", "data/codes/2/product.json"]


def test_data_keys_the_build_no_longer_writes_are_deleted_and_nothing_outside_data_is_touched(staging_dir: Path) -> None:
    write_built(staging_dir, {"locations.json": "same\n"})
    bucket = FakeBucket({
        "data/locations.json": b"same\n",
        "data/codes/gone/product.json": b"stale\n",
        "index.html": b"<html>\n",
        "database.json": b"not data\n",
    })

    publish_to_bucket(staging_dir, bucket)

    assert bucket.deletes() == ["data/codes/gone/product.json"]
    assert bucket.puts() == []
    assert bucket.objects == {"data/locations.json": b"same\n", "index.html": b"<html>\n", "database.json": b"not data\n"}


def test_meta_json_is_written_last_after_every_other_upload_and_delete(staging_dir: Path) -> None:
    write_built(staging_dir, {"meta.json": "new build\n", "locations.json": "changed\n", "z/last.json": "new\n"})
    bucket = FakeBucket({"data/locations.json": b"before\n", "data/stale.json": b"stale\n"})

    publish_to_bucket(staging_dir, bucket)

    assert bucket.calls[-1] == Put("data/meta.json", b"new build\n", content_type="application/json", cache_control="max-age=60")
    assert sorted(bucket.puts()[:-1]) == ["data/locations.json", "data/z/last.json"]
    assert bucket.deletes() == ["data/stale.json"]

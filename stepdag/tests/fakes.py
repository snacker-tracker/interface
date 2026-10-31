"""A fake S3, from moto, for the S3 bindings and the Lambda handlers."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import boto3
from moto import mock_aws


@contextmanager
def s3_bucket(name: str) -> Iterator[Any]:
    with mock_aws():
        client = boto3.client("s3", region_name="ap-southeast-1")
        client.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"})
        yield client

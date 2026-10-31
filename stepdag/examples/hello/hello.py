"""stepdag's hello-world graph: every feature of stepdag, on values small enough to read."""

import os
from typing import Any

from stepdag import UNCHANGED, Definitions, RunContext, asset
from stepdag.assets import Bindings
from stepdag.json_io import DirectoryStore, FixedJson, RunJson, S3Store, Store


@asset(io_manager="fixed_json")
def greeting(*, previous: str | None, context: RunContext) -> str:
    text = f"Hello, {context.config.get('name', 'world')}!"
    return UNCHANGED if text == previous else text


@asset(io_manager="fixed_json")
def counter(*, previous: int | None) -> int:
    return (previous or 0) + 1


@asset(deps=["greeting"], io_manager="run_json")
def shout(text: str) -> str:
    return text.upper()


@asset(deps=["greeting"], io_manager="run_json")
def word_count(text: str) -> int:
    return len(text.split())


def counted(value: dict[str, Any], context: RunContext) -> str | None:
    """Fails when the counter isn't above zero, or whenever the run config asks it to."""
    if context.config.get("fail_check"):
        return "the run config asked this check to fail"
    return None if value["count"] > 0 else f"count is {value['count']}"


@asset(deps=["shout", "word_count", "counter"], io_manager="run_json", checks=[counted])
def report(shouted: str, words: int, count: int) -> dict[str, Any]:
    return {"shout": shouted, "words": words, "count": count}


def _bindings(store: Store) -> Bindings:
    return {"run_json": RunJson(store), "fixed_json": FixedJson(store)}


def local_bindings() -> Bindings:
    """Values in `$STEPDAG_DIR`, or `.stepdag` in the current directory."""
    return _bindings(DirectoryStore(os.environ.get("STEPDAG_DIR", ".stepdag")))


def lambda_bindings() -> Bindings:
    """Values in the bucket `$STEPDAG_BUCKET`, which the hello graph's Terraform sets."""
    import boto3

    return _bindings(S3Store(boto3.client("s3"), os.environ["STEPDAG_BUCKET"]))


defs = Definitions(
    [greeting, counter, shout, word_count, report],
    environments={"local": local_bindings, "lambda": lambda_bindings},
)

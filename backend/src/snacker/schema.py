"""The output contract as JSON Schema, for readers of the static JSON that aren't this backend.

One schema holds every file document and shared row under `$defs`, named after its type
in the contract module, so shared rows are defined once. It is generated from the
contract types and committed at the repo root; the frontend's types are generated from it.
"""

import json
from functools import cache
from typing import Any, is_typeddict

from jsonschema import Draft202012Validator
from pydantic import ConfigDict, TypeAdapter
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import CoreSchema

from snacker import contract

DOCUMENTS = (
    contract.MetaFile,
    contract.LocationsFile,
    contract.IndexFile,
    contract.ScannersFile,
    contract.ProductFile,
    contract.CodeScansFile,
)
"""Every file document, in the order PRD.md §7.1 lists the files."""


class _UntitledFields(GenerateJsonSchema):
    """Leave out pydantic's per-field titles ("Office Time Zone"): they repeat the field
    name, and TypeScript generators would turn each into a named type."""

    def field_title_should_be_set(self, schema: CoreSchema) -> bool:
        return False


@cache
def contract_schema() -> dict[str, Any]:
    # Strict objects with field docstrings as descriptions. Set here rather than on each
    # type so the contract module stays plain TypedDicts.
    for value in vars(contract).values():
        if is_typeddict(value):
            value.__pydantic_config__ = ConfigDict(extra="forbid", use_attribute_docstrings=True)
    _, schema = TypeAdapter.json_schemas(
        [(document.__name__, "serialization", TypeAdapter(document)) for document in DOCUMENTS],
        ref_template="#/$defs/{model}",
        schema_generator=_UntitledFields,
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Snacker Tracker static JSON",
        "description": "Every file the build writes under data/ (see PRD.md §7). Each file is one of the "
        + ", ".join(document.__name__ for document in DOCUMENTS)
        + " documents in $defs. Generated from the backend's contract module: don't edit by hand.",
        **schema,
    }


def schema_json() -> str:
    return json.dumps(contract_schema(), ensure_ascii=False, indent=2) + "\n"


def schema_errors(document: str, content: Any) -> list[str]:
    """Where `content` breaks the `document` schema, e.g. "recent/0/code: None is not of type 'string'"."""
    validator = _validator(document)
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '(top level)'}: {error.message}"
        for error in sorted(validator.iter_errors(content), key=lambda error: list(map(str, error.absolute_path)))
    ]


@cache
def _validator(document: str) -> Draft202012Validator:
    defs = contract_schema()["$defs"]
    return Draft202012Validator({"$ref": f"#/$defs/{document}", "$defs": defs})

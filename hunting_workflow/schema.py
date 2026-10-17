"""Validate the deliberately small JSON Schema subset used by this package.

The shipped schemas are also usable with full Draft 2020-12 validators.
Only type, required, properties, additionalProperties, items, enum, minItems,
minLength and pattern are needed here. Unsupported keywords fail explicitly.
"""
import json
import re
from importlib.resources import files

META_KEYS = {"$schema", "$id", "title", "description", "examples", "default"}
RULE_KEYS = {"type", "required", "properties", "additionalProperties", "items", "enum",
             "minItems", "minLength", "pattern"}


def resource(kind, name):
    return json.loads(files("hunting_workflow").joinpath("resources", kind, name).read_text(encoding="utf-8"))


def validate(value, schema, path="$"):
    errors = []
    unknown = set(schema) - RULE_KEYS - META_KEYS
    if unknown:
        raise ValueError("Unsupported schema keywords: " + ", ".join(sorted(unknown)))
    kinds = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "boolean": lambda x: type(x) is bool,
             "integer": lambda x: type(x) is int, "number": lambda x: type(x) in (int, float),
             "null": lambda x: x is None}
    expected = schema.get("type")
    if expected and not kinds[expected](value):
        return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                errors.append(f"{path}.{key}: unknown property")
        for key, child in properties.items():
            if key in value:
                errors.extend(validate(value[key], child, path + "." + key))
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        for index, child in enumerate(value):
            if "items" in schema:
                errors.extend(validate(child, schema["items"], f"{path}[{index}]"))
    elif isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append(f"{path}: text is too short")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: invalid format")
    return errors

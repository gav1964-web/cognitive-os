"""JSON Schema validation for plugin contracts."""

from __future__ import annotations

import re
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - fallback is tested by behavior, not import state.
    jsonschema = None


class SchemaValidationError(ValueError):
    """Raised when payload does not match a plugin schema."""


def validate_payload(payload: Any, schema: dict[str, Any], *, label: str) -> None:
    if jsonschema is not None:
        try:
            jsonschema.validate(instance=payload, schema=schema)
            return
        except Exception as exc:
            raise SchemaValidationError(f"{label} schema validation failed: {exc}") from exc
    _validate_value(payload, schema, label=label)


def _validate_value(value: Any, schema: dict[str, Any], *, label: str) -> None:
    _reject_unsupported(schema, label)
    if "const" in schema and value != schema["const"]:
        raise SchemaValidationError(f"{label} must equal const value")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{label} must be one of the declared enum values")
    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_matches_type(value, item) for item in expected):
            raise SchemaValidationError(f"{label} must be one of: {', '.join(expected)}")
    elif expected is not None and not _matches_type(value, expected):
        raise SchemaValidationError(f"{label} must be {expected}")
    if isinstance(value, dict):
        _validate_object(value, schema, label)
    elif isinstance(value, list):
        _validate_array(value, schema, label)
    elif isinstance(value, str):
        _validate_string(value, schema, label)
    elif _is_number(value):
        _validate_number(value, schema, label)


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "number":
        return _is_number(value)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return False


def _validate_object(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in value:
            raise SchemaValidationError(f"{label} missing required key: {key}")
    if schema.get("additionalProperties") is False:
        unexpected = sorted(set(value) - set(properties))
        if unexpected:
            raise SchemaValidationError(f"{label} contains unexpected properties: {', '.join(unexpected)}")
    for key, item in value.items():
        if key in properties:
            _validate_value(item, properties[key], label=f"{label}.{key}")


def _validate_array(value: list[Any], schema: dict[str, Any], label: str) -> None:
    _bounded_length(value, schema, label, "Items")
    if schema.get("uniqueItems") and len({repr(item) for item in value}) != len(value):
        raise SchemaValidationError(f"{label} must contain unique items")
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(value):
            _validate_value(item, items, label=f"{label}[{index}]")


def _validate_string(value: str, schema: dict[str, Any], label: str) -> None:
    _bounded_length(value, schema, label, "Length")
    if "pattern" in schema and re.search(str(schema["pattern"]), value) is None:
        raise SchemaValidationError(f"{label} does not match required pattern")


def _validate_number(value: int | float, schema: dict[str, Any], label: str) -> None:
    checks = (
        ("minimum", lambda limit: value < limit, "greater than or equal to"),
        ("maximum", lambda limit: value > limit, "less than or equal to"),
        ("exclusiveMinimum", lambda limit: value <= limit, "greater than"),
        ("exclusiveMaximum", lambda limit: value >= limit, "less than"),
    )
    for key, comparison, message in checks:
        if key in schema and comparison(schema[key]):
            raise SchemaValidationError(f"{label} must be {message} {schema[key]}")


def _bounded_length(value: Any, schema: dict[str, Any], label: str, suffix: str) -> None:
    minimum = schema.get(f"min{suffix}")
    maximum = schema.get(f"max{suffix}")
    if minimum is not None and len(value) < minimum:
        raise SchemaValidationError(f"{label} is shorter than {minimum}")
    if maximum is not None and len(value) > maximum:
        raise SchemaValidationError(f"{label} is longer than {maximum}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _reject_unsupported(schema: dict[str, Any], label: str) -> None:
    supported = {
        "$schema", "title", "description", "default", "examples", "type", "enum", "const",
        "properties", "required", "additionalProperties", "items", "minimum", "maximum",
        "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern",
        "minItems", "maxItems", "uniqueItems",
    }
    unsupported = sorted(set(schema) - supported)
    if unsupported:
        raise SchemaValidationError(f"{label} uses unsupported fallback keywords: {', '.join(unsupported)}")

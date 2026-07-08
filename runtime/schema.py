"""JSON Schema validation for plugin contracts."""

from __future__ import annotations

from typing import Any

try:
    import jsonschema
except Exception:  # pragma: no cover - fallback is tested by behavior, not import state.
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
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(payload, dict):
            raise SchemaValidationError(f"{label} must be object")
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                raise SchemaValidationError(f"{label} missing required key: {key}")
        properties = schema.get("properties", {})
        for key, value in payload.items():
            if key in properties:
                _validate_value(value, properties[key], label=f"{label}.{key}")
        return
    _validate_value(payload, schema, label=label)


def _validate_value(value: Any, schema: dict[str, Any], *, label: str) -> None:
    expected = schema.get("type")
    if expected is None:
        return
    if isinstance(expected, list):
        if "null" in expected and value is None:
            return
        non_null = [item for item in expected if item != "null"]
        if any(_matches_type(value, item) for item in non_null):
            return
        raise SchemaValidationError(f"{label} must be one of: {', '.join(expected)}")
    if expected == "string" and not isinstance(value, str):
        raise SchemaValidationError(f"{label} must be string")
    if expected == "object" and not isinstance(value, dict):
        raise SchemaValidationError(f"{label} must be object")
    if expected == "number" and not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{label} must be number")
    if expected == "integer" and not isinstance(value, int):
        raise SchemaValidationError(f"{label} must be integer")
    if expected == "boolean" and not isinstance(value, bool):
        raise SchemaValidationError(f"{label} must be boolean")
    if expected == "array" and not isinstance(value, list):
        raise SchemaValidationError(f"{label} must be array")


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "number":
        return isinstance(value, (int, float))
    if expected == "integer":
        return isinstance(value, int)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    return False

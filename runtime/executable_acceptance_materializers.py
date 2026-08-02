"""Materialize config-backed executable acceptance fixtures."""

from __future__ import annotations

from typing import Any

from .executable_acceptance_policy import sample_value


def materialize(value: Any) -> Any:
    if isinstance(value, dict):
        fixture = value.get("__fixture__")
        if fixture == "callable_id_of":
            return lambda schema: schema.get("$id") if isinstance(schema, dict) else None
        if fixture == "callable_items":
            return lambda schema: schema.items() if hasattr(schema, "items") else []
        if fixture == "callable_identity":
            return lambda value, *args, **kwargs: value
        if fixture == "callable_float":
            return lambda value, *args, **kwargs: float(value)
        if fixture == "configparser_flake8_empty":
            parser = __import__("configparser").RawConfigParser()
            parser.add_section("flake8:local-plugins")
            return parser
        if fixture == "bytes_io_empty":
            return __import__("io").BytesIO(b"")
        if fixture == "bytes_empty":
            return b""
        if fixture == "dateutil_parserinfo_minimal":
            return type("Info", (), _PARSERINFO_METHODS)()
        if fixture == "dateutil_result":
            return type("Result", (), {"hour": None, "minute": None, "second": None, "microsecond": None})()
        if fixture == "dateutil_ymd":
            return type("YMD", (list,), _YMD_METHODS)()
        if fixture == "pytest_source_minimal":
            return type("Source", (), {"lines": ["x = 1"], "raw_lines": ["x = 1"], "__str__": _source_text})()
        if fixture == "networkx_graph_path":
            return _networkx_graph_path()
        return {key: materialize(_coerced_field_value(str(key), item)) for key, item in value.items()}
    if isinstance(value, list):
        return [materialize(item) for item in value]
    return value


def _coerced_field_value(field_name: str, value: Any) -> Any:
    if value != "sample":
        return value
    replacement = sample_value("", field_name)
    return replacement if replacement != "sample" else value


def _source_text(self: Any) -> str:
    return "\n".join(self.lines)


def _networkx_graph_path() -> Any:
    graph = __import__("networkx").Graph()
    graph.add_edge("a", "b", label="edge")
    graph.nodes["a"]["label"] = "a"
    graph.nodes["b"]["label"] = "b"
    return graph


_PARSERINFO_METHODS = {
    "hms": lambda self, value: None,
    "jump": lambda self, value: False,
    "ampm": lambda self, value: None,
    "month": lambda self, value: None,
}
_YMD_METHODS = {
    "append": lambda self, value, label=None: list.append(self, value),
    "could_be_day": lambda self, value: True,
}

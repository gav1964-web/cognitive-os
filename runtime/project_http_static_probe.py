"""Static HTTP route fallback when framework runtime cannot be adapted."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def static_http_route_probe(app_path: Path, probe: dict[str, Any]) -> dict[str, Any]:
    route = str(probe.get("route") or probe.get("path") or "")
    source = str(probe.get("source") or "")
    handler = source.split(":", 1)[1] if ":" in source else ""
    try:
        tree = ast.parse(app_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "skipped", "reason": f"static route parse failed: {type(exc).__name__}: {exc}"}
    if not _route_declared(tree, route, handler):
        return {"status": "skipped", "reason": "static route not declared"}
    payload = {"handler": handler or "route", "route": str(probe.get("path") or route or "/"), "status": "available"}
    return {
        "status": "ok",
        "app_path": app_path.as_posix(),
        "response": {
            "status_code": 200,
            "is_json": True,
            "json_kind": "object",
            "json_keys": ["handler", "route", "status"],
            "shape": {"kind": "object", "field_types": {"handler": "str", "route": "str", "status": "str"}},
            "sample": payload,
            "bytes": len(str(payload).encode("utf-8")),
        },
        "dependency_stubs": ["static_http_route_fallback"],
        "fallback_reason": "no supported app adapter",
    }


def _route_declared(tree: ast.Module, route: str, handler: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if handler and node.name != handler:
            continue
        if any(_decorator_route(decorator) == route for decorator in node.decorator_list):
            return True
    return False


def _decorator_route(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    if not isinstance(node.func, ast.Attribute):
        return ""
    if node.func.attr.lower() not in {"get", "post", "put", "delete", "patch", "route"}:
        return ""
    if not node.args:
        return ""
    first = node.args[0]
    return str(first.value) if isinstance(first, ast.Constant) and isinstance(first.value, str) else ""

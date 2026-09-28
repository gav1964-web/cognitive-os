"""Bridge from SystemKnowledgeIR to ProjectRebuildSpec."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .project_rebuild_behavior import collect_source_response_blueprints
from .system_knowledge_ir import build_system_knowledge_ir


def build_project_rebuild_ir(
    *,
    source_dir: Path,
    analyzer_outputs: dict[str, Any],
    source_python: Path | None = None,
    include_embedded: bool = True,
) -> dict[str, Any]:
    project_report = dict(analyzer_outputs["project_map_report"])
    ir = build_system_knowledge_ir(project_report=project_report, origin="source_project")
    embedded = _embedded_ir(source_dir) if include_embedded else {}
    if embedded:
        ir = _merge_embedded_ir(ir, embedded)
    ir["public_interfaces"] = _unique_interfaces(
        [*list(ir.get("public_interfaces", []) or []), *_route_interfaces_from_analyzer(analyzer_outputs)]
    )
    ir["source_project"] = source_dir.as_posix()
    ir["behavior_blueprints"] = collect_source_response_blueprints(source_dir, _ir_probe_spec(source_dir, ir), source_python)
    return ir


def build_rebuild_spec_from_ir(*, source_dir: Path, ir: dict[str, Any]) -> dict[str, Any]:
    identity = dict(ir.get("project_identity", {}))
    domain = dict(ir.get("domain_model", {}))
    interfaces = list(ir.get("public_interfaces", []) or [])
    routes = _routes_from_ir(interfaces, source_dir)
    data_artifacts = _data_artifacts_from_ir(ir) or _data_artifacts(source_dir)
    spec = {
        "artifact_type": "ProjectRebuildSpec",
        "source_project": source_dir.as_posix(),
        "source_ir_schema": ir.get("schema_version"),
        "target_name": f"{_target_name(identity, source_dir)}_x",
        "main_task": str(ir.get("purpose") or _main_task(routes)),
        "framework": _framework_from_ir(identity, domain),
        "entrypoints": _unique(_list(identity.get("entrypoints"))),
        "routes": routes,
        "supported_scenarios": _scenarios_from_ir(ir, routes),
        "data_artifacts": data_artifacts,
        "core_capabilities": _capabilities_from_ir(ir)[:8],
        "quality_targets": {
            "single_file_app_limit": 400,
            "source_project_read_only": True,
            "generated_project_can_compile": True,
            "comparison_report_required": True,
            "compiled_from_system_knowledge_ir": True,
        },
        "knowledge_traceability": list(ir.get("source_traceability", []) or [])[:20],
        "knowledge_ir_snapshot": _compact_ir_snapshot(ir),
    }
    spec["behavior_blueprints"] = list(ir.get("behavior_blueprints", []) or [])
    return spec


def _embedded_ir(source_dir: Path) -> dict[str, Any]:
    path = source_dir / ".cognitive_os" / "system_knowledge_ir.json"
    if not path.exists():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) and payload.get("artifact_type") == "SystemKnowledgeIR" else {}


def _merge_embedded_ir(ir: dict[str, Any], embedded: dict[str, Any]) -> dict[str, Any]:
    merged = dict(ir)
    for key in [
        "purpose",
        "project_identity",
        "public_interfaces",
        "domain_model",
        "behavior_contracts",
        "architecture_slices",
        "acceptance_tests",
        "source_traceability",
        "quality_targets",
    ]:
        if embedded.get(key):
            merged[key] = embedded[key]
    merged["origin"] = "source_project_embedded_ir"
    return merged


def _compact_ir_snapshot(ir: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "SystemKnowledgeIR",
        "schema_version": ir.get("schema_version"),
        "origin": ir.get("origin"),
        "purpose": ir.get("purpose"),
        "project_identity": ir.get("project_identity"),
        "public_interfaces": list(ir.get("public_interfaces", []) or [])[:40],
        "domain_model": ir.get("domain_model"),
        "behavior_contracts": list(ir.get("behavior_contracts", []) or [])[:40],
        "architecture_slices": list(ir.get("architecture_slices", []) or [])[:40],
        "acceptance_tests": list(ir.get("acceptance_tests", []) or [])[:40],
        "source_traceability": list(ir.get("source_traceability", []) or [])[:40],
        "quality_targets": ir.get("quality_targets"),
    }


def _ir_probe_spec(source_dir: Path, ir: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "ProjectRebuildSpec",
        "source_project": source_dir.as_posix(),
        "target_name": f"{source_dir.name}_x",
        "main_task": str(ir.get("purpose") or ""),
        "entrypoints": _unique(_list(dict(ir.get("project_identity", {})).get("entrypoints"))),
        "routes": _routes_from_ir(list(ir.get("public_interfaces", []) or []), source_dir),
        "data_artifacts": _data_artifacts_from_ir(ir) or _data_artifacts(source_dir),
        "core_capabilities": _capabilities_from_ir(ir)[:8],
    }


def _routes_from_ir(interfaces: list[dict[str, Any]], source_dir: Path | None = None) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for interface in interfaces:
        if not isinstance(interface, dict) or interface.get("kind") != "route":
            continue
        route = str(interface.get("name") or "")
        if not route or route in seen:
            continue
        seen.add(route)
        source = interface.get("source")
        rows.append(
            {
                "route": route,
                "function": _route_function_name(interface, len(rows)),
                "methods": _list(interface.get("methods")) or ["GET"],
                "source": source,
                "response_kind": _route_response_kind(source_dir, source),
            }
        )
    return rows[:12]


def _route_interfaces_from_analyzer(analyzer_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    python_structure = dict(analyzer_outputs.get("extract_python_structure", {}))
    return [
        {
            "kind": "route",
            "name": route.get("route"),
            "function": route.get("function"),
            "methods": route.get("methods", []),
            "source": route.get("source"),
        }
        for route in _active_routes(python_structure.get("routes", []))
    ]


def _active_routes(routes: object) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for route in routes if isinstance(routes, list) else []:
        if not isinstance(route, dict) or str(route.get("path", "")).startswith("map_install_package/"):
            continue
        key = str(route.get("route") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "route": key,
                "function": route.get("function"),
                "methods": route.get("methods", []),
                "source": f"{route.get('path')}:{route.get('function')}",
            }
        )
    return rows[:12]


def _unique_interfaces(interfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for interface in interfaces:
        if not isinstance(interface, dict):
            continue
        key = (interface.get("kind"), interface.get("name"))
        if not interface.get("name") or key in seen:
            continue
        seen.add(key)
        result.append(interface)
    return result


def _route_function_name(interface: dict[str, Any], index: int) -> str:
    candidate = str(interface.get("function") or "").strip()
    if candidate:
        return candidate
    route = str(interface.get("name") or "").strip("/").replace("/", "_").replace("-", "_")
    return route or f"route_{index + 1}"


def _route_response_kind(source_dir: Path | None, source: object) -> str:
    if source_dir is None or not source:
        return "generic"
    path_text, _, function = str(source).partition(":")
    path = source_dir / path_text
    if not path.exists() or not function:
        return "generic"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return "generic"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function:
            calls = {_call_name(item) for item in ast.walk(node) if isinstance(item, ast.Call)}
            if "html" in calls:
                return "html"
            if "redirect" in calls:
                return "redirect"
            if calls.intersection({"json", "jsonify", "response.json"}):
                return "json"
    return "generic"


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
        return func.attr
    return ""


def _data_artifacts_from_ir(ir: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in _list(dict(ir.get("domain_model", {})).get("data_artifacts")):
        rows.append(item if isinstance(item, dict) else {"path": str(item), "exists": True, "size": 0})
    return rows


def _data_artifacts(source_dir: Path) -> list[dict[str, Any]]:
    names = ["kursk_vector_map.json", "kursk_nodes.json", "incidents.json", "branches_atms.json"]
    return [
        {"path": name, "exists": (source_dir / name).exists(), "size": (source_dir / name).stat().st_size}
        if (source_dir / name).exists()
        else {"path": name, "exists": False, "size": 0}
        for name in names
    ]


def _capabilities_from_ir(ir: dict[str, Any]) -> list[str]:
    capabilities = []
    for row in list(ir.get("behavior_contracts", []) or []):
        source = row.get("source") if isinstance(row, dict) else None
        if source:
            capabilities.append(str(source))
    for row in list(ir.get("architecture_slices", []) or []):
        if isinstance(row, dict) and row.get("id"):
            capabilities.append(str(row["id"]))
    return _unique(capabilities)


def _framework_from_ir(identity: dict[str, Any], domain: dict[str, Any]) -> str:
    frameworks = [str(item) for item in [*_list(identity.get("frameworks")), *_list(domain.get("frameworks"))]]
    if "Flask-like Python web app" in frameworks or "Flask" in frameworks:
        return "Flask-like Python web app"
    if "FastAPI" in frameworks:
        return "FastAPI Python web app"
    return "Python app"


def _target_name(identity: dict[str, Any], source_dir: Path) -> str:
    name = str(identity.get("name") or "").strip()
    return source_dir.name if name in {"", "unknown_project"} else name


def _scenarios_from_ir(ir: dict[str, Any], routes: list[dict[str, Any]]) -> list[str]:
    criteria = [
        str(row.get("criterion"))
        for row in list(ir.get("acceptance_tests", []) or [])
        if isinstance(row, dict) and row.get("criterion")
    ]
    return _unique([*criteria, *_scenarios(routes)])[:8]


def _main_task(routes: list[dict[str, Any]]) -> str:
    route_names = ", ".join(str(route.get("route")) for route in routes[:5])
    return f"Reproduce the source project behavior from SystemKnowledgeIR ({route_names})."


def _scenarios(routes: list[dict[str, Any]]) -> list[str]:
    route_set = {str(route.get("route")) for route in routes}
    scenarios = []
    if "/search" in route_set:
        scenarios.append("Search map objects by text query.")
    if "/get_incidents" in route_set:
        scenarios.append("Serve incident features and incident metadata.")
    if "/branches_atms" in route_set:
        scenarios.append("Serve branch and ATM GeoJSON overlays.")
    return scenarios


def _unique(items: list[Any]) -> list[str]:
    result = []
    for item in items:
        value = str(item)
        if value and value not in result:
            result.append(value)
    return result


def _list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, tuple):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, set):
        return sorted(item for item in value if item is not None and item != "")
    text = str(value).strip()
    return [text] if text else []

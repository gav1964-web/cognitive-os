"""Compact deterministic facts for project-analysis LLM layers."""

from __future__ import annotations

from typing import Any


def facts_from_project_report(report: dict[str, Any]) -> dict[str, Any]:
    outputs = dict(report.get("execution", {}).get("outputs", {}))
    project_report = dict(outputs.get("project_map_report", {}))
    python_structure = dict(outputs.get("extract_python_structure", {}))
    runtime_commands = dict(outputs.get("extract_runtime_commands", {}))
    answers = dict(project_report.get("answers", {}))
    insights = dict(python_structure.get("project_insights", {}))
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    contracts = dict(answers.get("4_contracts_data", {}))
    errors = dict(answers.get("5_errors_state_repro", {}))
    runtime_extraction = dict(answers.get("6_runtime_extraction_readiness", {}))
    summary = project_report.get("summary", {})
    central_flow_nodes = _compact_nodes(execution.get("central_flow_nodes", []), limit=8)
    implicit_orchestration = _compact_nodes(execution.get("implicit_orchestration", []), limit=8)
    internal_import_hubs = _compact_import_hubs(execution.get("internal_import_hubs", []), limit=8)
    too_broad_functions = _compact_nodes(capabilities.get("too_broad_functions", []), limit=8)
    weak_contract_zones = contracts.get("weak_contract_zones", [])[:12]
    routes = _compact_routes(python_structure.get("routes", []), limit=12)
    test_surface = insights.get("test_surface", {})
    return {
        "goal_id": report.get("goal_id"),
        "summary": summary,
        "risks": project_report.get("risks", [])[:8],
        "scope": {
            "main_task": scope.get("main_task"),
            "supported_scenarios": scope.get("supported_scenarios", [])[:5],
            "inputs": scope.get("inputs", [])[:8],
            "outputs": scope.get("outputs", [])[:8],
            "test_surface": scope.get("test_surface", {}),
        },
        "execution": {
            "entrypoints": execution.get("entrypoints", [])[:8],
            "central_flow_nodes": central_flow_nodes,
            "implicit_orchestration": implicit_orchestration,
            "internal_import_hubs": internal_import_hubs,
            "pipeline_candidate": execution.get("pipeline_candidate", [])[:8],
        },
        "capabilities": {
            "atomic_reusable_capabilities": capabilities.get("atomic_reusable_capabilities", [])[:10],
            "pure_transforms": _compact_nodes(capabilities.get("pure_transforms", []), limit=8),
            "too_broad_functions": too_broad_functions,
            "environment_dependencies": capabilities.get("environment_dependencies", {}),
            "fallback_logic": capabilities.get("fallback_logic", [])[:6],
        },
        "contracts": {
            "explicit_schemas": _compact_schema_rows(contracts.get("explicit_schemas", []), limit=10),
            "schema_fields": _compact_schema_fields(contracts.get("schema_fields", []), limit=8),
            "weak_contract_zones": weak_contract_zones,
            "auto_contract_feasibility": contracts.get("auto_contract_feasibility"),
        },
        "errors_state_repro": {
            "likely_error_types": errors.get("likely_error_types", [])[:10],
            "explicit_error_handling": errors.get("explicit_error_handling", [])[:10],
            "error_details": _compact_error_details(errors.get("error_details", {})),
            "state_to_preserve": errors.get("state_to_preserve", [])[:8],
            "reproducibility": errors.get("reproducibility"),
            "minimal_cognitive_loop": errors.get("minimal_cognitive_loop", [])[:8],
        },
        "runtime_extraction": {
            "data_lifecycle": runtime_extraction.get("data_lifecycle", [])[:8],
            "mixed_responsibility_functions": _compact_mixed(runtime_extraction.get("mixed_responsibility_functions", []), limit=8),
            "hidden_orchestrators": _compact_nodes(runtime_extraction.get("hidden_orchestrators", []), limit=8),
            "long_lived_state": runtime_extraction.get("long_lived_state", [])[:8],
            "idempotency_risks": runtime_extraction.get("idempotency_risks", [])[:8],
            "quarantine_candidates": runtime_extraction.get("quarantine_candidates", [])[:8],
            "process_boundary_candidates": runtime_extraction.get("process_boundary_candidates", [])[:8],
            "contract_test_strategy": runtime_extraction.get("contract_test_strategy", {}),
            "resume_reuse_plan": runtime_extraction.get("resume_reuse_plan", [])[:8],
            "minimal_extraction_plan": _compact_extraction_plan(runtime_extraction.get("minimal_extraction_plan")),
        },
        "routes": routes,
        "runtime_commands": _compact_commands(runtime_commands.get("commands", []), limit=8),
        "test_surface": test_surface,
        "external_imports": insights.get("external_imports", [])[:12],
        "subsystems": _subsystems(summary, routes, central_flow_nodes, too_broad_functions, weak_contract_zones, internal_import_hubs, test_surface),
        "architectural_hotspots": _architectural_hotspots(central_flow_nodes, too_broad_functions, weak_contract_zones, internal_import_hubs),
        "ownership_boundaries": _ownership_boundaries(summary, routes, internal_import_hubs, project_report.get("risks", [])[:8]),
    }


def llm_fact_digest(facts: dict[str, Any]) -> dict[str, Any]:
    summary = dict(facts.get("summary", {}))
    scope = dict(facts.get("scope", {}))
    execution = dict(facts.get("execution", {}))
    capabilities = dict(facts.get("capabilities", {}))
    contracts = dict(facts.get("contracts", {}))
    errors = dict(facts.get("errors_state_repro", {}))
    runtime_extraction = dict(facts.get("runtime_extraction", {}))
    return {
        "root": summary.get("root"),
        "frameworks": summary.get("frameworks", []),
        "files": summary.get("file_count"),
        "dirs": summary.get("directory_count"),
        "routes_count": summary.get("routes"),
        "task": scope.get("main_task"),
        "scenarios": scope.get("supported_scenarios", [])[:4],
        "inputs": scope.get("inputs", [])[:5],
        "outputs": scope.get("outputs", [])[:5],
        "entrypoints": execution.get("entrypoints", [])[:5],
        "central": _node_refs(execution.get("central_flow_nodes", []), limit=4),
        "broad": _node_refs(capabilities.get("too_broad_functions", []), limit=4),
        "capabilities": capabilities.get("atomic_reusable_capabilities", [])[:8],
        "schemas": contracts.get("explicit_schemas", [])[:8],
        "weak_contracts": contracts.get("weak_contract_zones", [])[:6],
        "errors": errors.get("likely_error_types", [])[:8],
        "handlers": dict(errors.get("error_details", {})).get("handlers", [])[:8],
        "loop": errors.get("minimal_cognitive_loop", [])[:6],
        "tests": facts.get("test_surface", {}),
        "risks": [risk.get("code") for risk in facts.get("risks", [])[:6]],
        "subsystems": facts.get("subsystems", [])[:6],
        "hotspots": facts.get("architectural_hotspots", [])[:8],
        "boundaries": facts.get("ownership_boundaries", [])[:6],
        "runtime_extraction": {
            "mixed": _node_refs(runtime_extraction.get("mixed_responsibility_functions", []), limit=4),
            "orchestrators": _node_refs(runtime_extraction.get("hidden_orchestrators", []), limit=4),
            "idempotency": runtime_extraction.get("idempotency_risks", [])[:4],
            "quarantine": runtime_extraction.get("quarantine_candidates", [])[:4],
            "process_boundary": runtime_extraction.get("process_boundary_candidates", [])[:4],
            "resume": runtime_extraction.get("resume_reuse_plan", [])[:4],
            "extraction": _compact_extraction_plan(runtime_extraction.get("minimal_extraction_plan")),
        },
    }


def _compact_nodes(nodes: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [
        {
            "path": node.get("path"),
            "name": node.get("name"),
            "line": node.get("line"),
            "loc": node.get("loc"),
            "call_count": node.get("call_count"),
            "side_effects": node.get("side_effects", []),
        }
        for node in nodes[:limit]
    ]


def _compact_import_hubs(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [{"path": row.get("path"), "internal_import_count": row.get("internal_import_count")} for row in rows[:limit]]


def _compact_schema_rows(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    return [f"{row.get('path')}:{row.get('name')}" for row in rows[:limit]]


def _compact_schema_fields(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [{"path": row.get("path"), "class": row.get("class"), "field_count": len(row.get("fields", []))} for row in rows[:limit]]


def _compact_error_details(details: dict[str, Any]) -> dict[str, Any]:
    return {
        "raises": details.get("raises", [])[:12],
        "handlers": details.get("handlers", [])[:12],
        "functions_with_try": details.get("functions_with_try", [])[:12],
    }


def _compact_routes(routes: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [{"methods": route.get("methods", []), "route": route.get("route"), "path": route.get("path"), "function": route.get("function")} for route in routes[:limit]]


def _compact_commands(commands: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [{"path": command.get("path"), "purpose": command.get("purpose")} for command in commands[:limit]]


def _compact_mixed(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return [
        {
            "path": row.get("path"),
            "name": row.get("name"),
            "line": row.get("line"),
            "loc": row.get("loc"),
            "responsibilities": row.get("responsibilities", []),
        }
        for row in rows[:limit]
    ]


def _compact_extraction_plan(plan: Any) -> list[dict[str, Any]]:
    if isinstance(plan, dict):
        rows = plan.get("capabilities_to_extract", [])
        return rows[:5] if isinstance(rows, list) else []
    if isinstance(plan, list):
        return plan[:5]
    return []


def _node_refs(nodes: list[dict[str, Any]], *, limit: int) -> list[str]:
    refs = []
    for node in nodes[:limit]:
        ref = f"{node.get('path')}:{node.get('name')}"
        if node.get("loc"):
            ref += f"({node.get('loc')} loc)"
        refs.append(ref)
    return refs


def _subsystems(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    central_nodes: list[dict[str, Any]],
    broad_nodes: list[dict[str, Any]],
    weak_contracts: list[str],
    import_hubs: list[dict[str, Any]],
    test_surface: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in list(summary.get("read_files", []) or []) + list(summary.get("entrypoints", []) or []):
        _touch_subsystem(rows, _subsystem_name(str(path)), "file")
    for route in routes:
        name = _subsystem_name(str(route.get("path") or ""))
        _touch_subsystem(rows, name, "route")
    for node in central_nodes:
        name = _subsystem_name(str(node.get("path") or ""))
        _touch_subsystem(rows, name, "central")
    for node in broad_nodes:
        name = _subsystem_name(str(node.get("path") or ""))
        _touch_subsystem(rows, name, "broad")
    for item in weak_contracts:
        name = _subsystem_name(str(item).split(":", 1)[0])
        _touch_subsystem(rows, name, "weak_contract")
    for hub in import_hubs:
        name = _subsystem_name(str(hub.get("path") or ""))
        _touch_subsystem(rows, name, "import_hub")
    for row in rows.values():
        row["score"] = row["routes"] * 3 + row["central"] * 3 + row["broad"] * 4 + row["weak_contracts"] * 2 + row["import_hubs"] * 2 + row["files"]
        row["test_files_seen"] = test_surface.get("test_files_seen", test_surface.get("test_files", 0))
    return sorted(rows.values(), key=lambda item: (-item["score"], item["name"]))[:8]


def _touch_subsystem(rows: dict[str, dict[str, Any]], name: str, kind: str) -> None:
    if not name:
        return
    row = rows.setdefault(
        name,
        {"name": name, "files": 0, "routes": 0, "central": 0, "broad": 0, "weak_contracts": 0, "import_hubs": 0},
    )
    if kind == "file":
        row["files"] += 1
    elif kind == "route":
        row["routes"] += 1
    elif kind == "central":
        row["central"] += 1
    elif kind == "broad":
        row["broad"] += 1
    elif kind == "weak_contract":
        row["weak_contracts"] += 1
    elif kind == "import_hub":
        row["import_hubs"] += 1


def _architectural_hotspots(
    central_nodes: list[dict[str, Any]],
    broad_nodes: list[dict[str, Any]],
    weak_contracts: list[str],
    import_hubs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hotspots = []
    for node in broad_nodes[:5]:
        hotspots.append({"kind": "broad_function", "target": _node_ref(node), "weight": node.get("loc") or node.get("call_count") or 1})
    for node in central_nodes[:5]:
        hotspots.append({"kind": "central_flow", "target": _node_ref(node), "weight": node.get("call_count") or node.get("loc") or 1})
    for contract in weak_contracts[:6]:
        hotspots.append({"kind": "weak_contract", "target": contract, "weight": 2})
    for hub in import_hubs[:5]:
        hotspots.append({"kind": "import_hub", "target": hub.get("path"), "weight": hub.get("internal_import_count") or 1})
    return sorted(hotspots, key=lambda item: (-int(item.get("weight") or 0), str(item.get("target"))))[:10]


def _ownership_boundaries(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    import_hubs: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    boundaries = []
    entrypoints = summary.get("entrypoints", []) or []
    if len(entrypoints) > 1:
        boundaries.append({"kind": "multiple_entrypoints", "target": ", ".join(str(item) for item in entrypoints[:4])})
    route_subsystems = sorted({_subsystem_name(str(route.get("path") or "")) for route in routes if route.get("path")})
    if len(route_subsystems) > 1:
        boundaries.append({"kind": "routes_cross_subsystems", "target": ", ".join(route_subsystems[:5])})
    for hub in import_hubs[:3]:
        boundaries.append({"kind": "import_hub_boundary", "target": str(hub.get("path"))})
    if any(risk.get("code") == "packaged_copy_detected" for risk in risks):
        boundaries.append({"kind": "packaged_copy", "target": "map_install_package"})
    return boundaries[:8]


def _subsystem_name(path: str) -> str:
    clean = path.replace("\\", "/").strip("/")
    if not clean:
        return ""
    parts = clean.split("/")
    if parts[0] in {"app", "src", "p0048"} and len(parts) > 1:
        return "/".join(parts[:2])
    if parts[0] in {"tests", "tools", "plugins"} and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def _node_ref(node: dict[str, Any]) -> str:
    path = node.get("path")
    name = node.get("name")
    return f"{path}:{name}" if name else str(path)

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
        "domain_anchors": _domain_anchor_refs(python_structure, scope.get("domain_profile", {}), limit=12),
        "scope": {
            "main_task": scope.get("main_task"),
            "supported_scenarios": scope.get("supported_scenarios", [])[:5],
            "inputs": scope.get("inputs", [])[:8],
            "outputs": scope.get("outputs", [])[:8],
            "test_surface": scope.get("test_surface", {}),
            "domain_profile": scope.get("domain_profile", {}),
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
        "domain_profile": scope.get("domain_profile", {}),
        "scenarios": scope.get("supported_scenarios", [])[:4],
        "inputs": scope.get("inputs", [])[:5],
        "outputs": scope.get("outputs", [])[:5],
        "entrypoints": execution.get("entrypoints", [])[:5],
        "routes": facts.get("routes", [])[:8],
        "domain_anchors": facts.get("domain_anchors", [])[:10],
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

def _domain_anchor_refs(python_structure: dict[str, Any], domain_profile: dict[str, Any], *, limit: int) -> list[str]:
    kind = str(domain_profile.get("kind") or "").lower()
    if kind == "multi_agent_orchestration_runtime":
        preferred = {
            "run_consensus",
            "execute_pipeline",
            "_execute_pipeline_background",
            "_execute_group",
            "execute_group",
            "create_task",
            "send_task",
            "broadcast_group_update",
            "handle_message",
            "register_agent",
        }
        refs = []
        for file_row in python_structure.get("files", []):
            path = str(file_row.get("path") or "")
            if not path or _is_contextual_path(path):
                continue
            if not any(token in path.lower() for token in ("orchestrator", "consensus", "a2a_protocol", "api/main", "websockets")):
                continue
            for function in file_row.get("functions", []):
                name = str(function.get("name") or "")
                if name in preferred or any(token in name.lower() for token in ("consensus", "pipeline", "group", "task", "message")):
                    refs.append(_node_ref({"path": path, "name": name, "loc": function.get("loc")}))
        return sorted(set(refs), key=lambda ref: (_multi_agent_anchor_priority(ref), ref))[:limit]
    if kind == "llm_provider_gateway" or _has_chat_completion_route(python_structure):
        refs = []
        for route in python_structure.get("routes", []):
            if not isinstance(route, dict):
                continue
            route_text = str(route.get("route") or "")
            function = str(route.get("function") or "")
            path = str(route.get("path") or "")
            if "chat/completions" in route_text or "chat_completions" in function or "_handle_chat_request" in function:
                refs.append(f"{path}:{function} {route_text}".strip())
        for file_row in python_structure.get("files", []):
            path = str(file_row.get("path") or "")
            if not path or _is_contextual_path(path):
                continue
            for function in file_row.get("functions", []):
                name = str(function.get("name") or "")
                if name in {"chat_completions", "_handle_chat_request", "build_providers_from_config", "select_provider"}:
                    refs.append(_node_ref({"path": path, "name": name, "loc": function.get("loc")}))
        return sorted(set(refs))[:limit]
    if kind != "llm_auto_repair_loop":
        return []
    preferred = {
        "send_to_model",
        "extract_json_from_model_response",
        "write_files",
        "docker_run",
        "docker_build",
        "goal_to_spec",
        "check_single_module_output",
        "clean_module_output",
        "regenerate_module",
        "fix_module_until_success",
    }
    refs = []
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "")
        if not path or _is_contextual_path(path):
            continue
        for function in file_row.get("functions", []):
            name = str(function.get("name") or "")
            if name in preferred:
                refs.append(_node_ref({"path": path, "name": name, "loc": function.get("loc")}))
    return sorted(set(refs), key=lambda ref: (_repair_anchor_priority(ref), ref))[:limit]

def _multi_agent_anchor_priority(ref: str) -> int:
    lowered = ref.lower()
    priority = (
        "core/orchestrator/orchestrator.py",
        "core/orchestrator/group_manager.py",
        "core/consensus/engine.py:run_consensus",
        "core/a2a_protocol/protocol.py",
        "api/main.py:_execute_pipeline_background",
    )
    for index, token in enumerate(priority):
        if token in lowered:
            return index
    return 99

def _has_chat_completion_route(python_structure: dict[str, Any]) -> bool:
    for route in python_structure.get("routes", []) or []:
        if not isinstance(route, dict):
            continue
        route_text = str(route.get("route") or "").lower()
        function = str(route.get("function") or "").lower()
        if "chat/completions" in route_text or "chat_completions" in function:
            return True
    return False

def _node_refs(nodes: list[dict[str, Any]], *, limit: int) -> list[str]:
    refs = []
    for node in nodes[:limit]:
        ref = f"{node.get('path')}:{node.get('name')}"
        if node.get("loc"):
            ref += f"({node.get('loc')} loc)"
        refs.append(ref)
    return refs

def _repair_anchor_priority(ref: str) -> int:
    name = ref.split(":", 1)[-1].split("(", 1)[0]
    priority = {
        "send_to_model": 0,
        "extract_json_from_model_response": 1,
        "write_files": 2,
        "check_single_module_output": 3,
        "clean_module_output": 4,
        "goal_to_spec": 5,
        "regenerate_module": 6,
        "fix_module_until_success": 7,
        "docker_run": 8,
        "docker_build": 9,
    }
    return priority.get(name, 50)

def _is_contextual_path(path: str) -> bool:
    parts = path.lower().replace("\\", "/").split("/")
    return any(part in {"test", "tests", "example", "examples", "dist", "build"} or part.startswith(("generated_", "generated-")) for part in parts)

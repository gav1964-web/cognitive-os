"""Question-oriented project analysis answers."""

from __future__ import annotations

from typing import Any

from .core_paths import is_core_path
from .doc_purpose import docs_text, purpose_heading, purpose_sentence
from .runtime_readiness import (
    best_effort_dataflows,
    contract_test_strategy,
    data_lifecycle,
    evidence_claims,
    hidden_orchestrators,
    idempotency_risks,
    long_lived_state,
    minimal_extraction_plan,
    mixed_responsibility_functions,
    process_boundary_candidates,
    quarantine_candidates,
    resume_reuse_plan,
    source_strata,
)


def build_answers(
    summary: dict[str, Any],
    risks: list[dict[str, str]],
    stack: dict[str, Any],
    files: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
) -> dict[str, Any]:
    routes = python_structure.get("routes", [])
    commands = _active_commands(runtime_commands.get("commands", []))
    imports = set(python_structure.get("imports", []))
    insights = dict(python_structure.get("project_insights", {}))
    docs = docs_text(files)
    project_type = _project_type(summary, imports)
    return {
        "1_scope": {
            "main_task": _main_task(project_type, summary, docs),
            "supported_scenarios": _scenarios(summary, routes, commands),
            "inputs": _inputs(routes, commands, imports),
            "outputs": _outputs(routes, commands, imports, stack),
            "code_areas": _code_areas(python_structure),
            "test_surface": insights.get("test_surface", {}),
        },
        "2_execution": {
            "entrypoints": summary.get("entrypoints", []),
            "runtime_commands": [_command_summary(command) for command in commands[:10]],
            "primary_execution_path": _execution_path(summary, routes, commands),
            "central_flow_nodes": _active_nodes(python_structure.get("central_nodes", []))[:8],
            "implicit_orchestration": _active_nodes(python_structure.get("wide_functions", []))[:8],
            "internal_import_hubs": _active_nodes(insights.get("import_graph", []))[:8],
            "pipeline_candidate": _pipeline_candidate(summary, routes, commands),
        },
        "3_capabilities": {
            "atomic_reusable_capabilities": _capability_candidates(python_structure, routes, commands),
            "pure_transforms": _core_pure_transforms(python_structure),
            "too_broad_functions": _active_nodes(python_structure.get("wide_functions", []))[:8],
            "environment_dependencies": python_structure.get("external_dependencies", {}),
            "fallback_logic": _fallback_logic(python_structure, docs),
        },
        "4_contracts_data": {
            "main_data_structures": _data_structures(python_structure),
            "explicit_schemas": dict(python_structure.get("contracts", {})).get("schema_like_classes", []),
            "schema_fields": insights.get("schema_fields", [])[:8],
            "weak_contract_zones": _weak_contract_zones(python_structure),
            "artifacts_to_persist": _artifacts_to_persist(imports, stack),
            "auto_contract_feasibility": _auto_contract_feasibility(python_structure),
        },
        "5_errors_state_repro": {
            "likely_error_types": _likely_error_types(risks, imports),
            "explicit_error_handling": _error_handling_hints(python_structure),
            "error_details": insights.get("error_handling", {}),
            "state_to_preserve": _state_to_preserve(imports, stack),
            "reproducibility": _reproducibility(files, stack, commands),
            "minimal_cognitive_loop": _minimal_loop(routes, commands),
        },
        "6_runtime_extraction_readiness": {
            "data_lifecycle": data_lifecycle(project_type, routes, commands, python_structure),
            "dataflows": best_effort_dataflows(python_structure),
            "evidence_claims": evidence_claims(python_structure),
            "mixed_responsibility_functions": mixed_responsibility_functions(python_structure),
            "hidden_orchestrators": hidden_orchestrators(python_structure),
            "long_lived_state": long_lived_state(imports, stack, python_structure),
            "idempotency_risks": idempotency_risks(python_structure),
            "quarantine_candidates": quarantine_candidates(risks, imports, python_structure),
            "process_boundary_candidates": process_boundary_candidates(python_structure),
            "contract_test_strategy": contract_test_strategy(python_structure),
            "resume_reuse_plan": resume_reuse_plan(routes, commands, imports),
            "minimal_extraction_plan": minimal_extraction_plan(python_structure, routes, commands),
            "source_strata": source_strata(python_structure),
        },
    }


def _active_commands(commands: Any) -> list[dict[str, Any]]:
    if not isinstance(commands, list):
        return []
    return [
        command
        for command in commands
        if isinstance(command, dict) and is_core_path(str(command.get("path", "")))
    ]


def _active_nodes(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict) and is_core_path(str(row.get("path", "")))
    ]


def inline_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "none"
        return "; ".join(inline_value(item) for item in value[:8])
    if isinstance(value, dict):
        return "; ".join(f"{key}={inline_value(val)}" for key, val in list(value.items())[:8])
    return str(value)


def _project_type(summary: dict[str, Any], imports: set[str]) -> str:
    frameworks = set(summary.get("frameworks", []))
    if "FastAPI" in frameworks:
        return "FastAPI API service"
    if "Flask-like Python web app" in frameworks:
        return "Flask web application"
    if "sqlite3" in imports or summary.get("entrypoints"):
        return "Python automation/tooling project"
    return "Python project"


def _main_task(project_type: str, summary: dict[str, Any], docs: str) -> str:
    if docs:
        sentence = purpose_sentence(docs)
        if sentence:
            return f"Inferred from docs: {sentence} ({project_type})."
        heading = purpose_heading(docs)
        if heading:
            return f"Inferred from docs: {heading} ({project_type})."
    if project_type == "FastAPI API service":
        return "Expose an HTTP API service and return structured JSON responses."
    if project_type == "Flask web application":
        return "Serve a web application with HTTP endpoints and browser-facing data/API responses."
    entrypoints = ", ".join(summary.get("entrypoints", [])[:3])
    return f"Run project-specific Python workflows through detected entrypoints ({entrypoints})."


def _scenarios(summary: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    scenarios = []
    route_names = {route.get("route") for route in routes}
    if routes:
        scenarios.append(f"Serve HTTP API/web requests across {len(routes)} detected routes.")
    if any(command.get("purpose") == "install_dependencies" for command in commands):
        scenarios.append("Install project dependencies from runtime scripts.")
    if any(command.get("purpose") == "run_application" for command in commands):
        scenarios.append("Start the application from a local runtime script.")
    if any(command.get("purpose") == "rebuild_data" for command in commands):
        scenarios.append("Rebuild derived data artifacts from scripts.")
    if "/v1/chat/completions" in route_names or "/chat" in route_names:
        scenarios.append("Handle chat/completion API requests.")
    if not scenarios and summary.get("entrypoints"):
        scenarios.append("Run CLI/tooling entrypoints detected in the project tree.")
    return scenarios[:5]


def _inputs(routes: list[dict[str, Any]], commands: list[dict[str, Any]], imports: set[str]) -> list[str]:
    inputs = []
    if routes:
        inputs.append("HTTP requests")
    if commands:
        inputs.append("CLI/script invocation")
    if imports & {"json", "csv", "openpyxl", "zipfile"}:
        inputs.append("files or structured documents")
    if imports & {"requests", "httpx", "openai"}:
        inputs.append("external API responses")
    return inputs or ["not enough evidence"]


def _outputs(routes: list[dict[str, Any]], commands: list[dict[str, Any]], imports: set[str], stack: dict[str, Any]) -> list[str]:
    outputs = []
    if routes:
        outputs.append("HTTP/API responses")
    if imports & {"json", "csv", "openpyxl", "zipfile"}:
        outputs.append("files or serialized artifacts")
    if imports & {"sqlite3", "sqlalchemy"}:
        outputs.append("database state")
    if commands or stack.get("large_artifacts"):
        outputs.append("side effects in local filesystem")
    return outputs or ["not enough evidence"]


def _code_areas(python_structure: dict[str, Any]) -> dict[str, list[str]]:
    paths = [str(item.get("path", "")) for item in python_structure.get("files", [])]
    active = [path for path in paths if is_core_path(path)]
    return {
        "core_logic": active[:10],
        "interfaces_adapters": [
            path
            for path in active
            if any(part in path.lower() for part in ("api", "server", "client", "adapter", "app.py"))
        ][:10],
        "tests": [path for path in paths if path.startswith("tests/") or "/test" in path][:10],
        "experiments_tools": [path for path in paths if path.startswith(("tools/", "scratch/", "examples/"))][:10],
    }


def _command_summary(command: dict[str, Any]) -> dict[str, str]:
    return {"path": str(command.get("path")), "purpose": str(command.get("purpose")), "command": _representative_command(command.get("commands") or [])}


def _execution_path(summary: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    if routes:
        return ["HTTP request", "framework router", "route handler", "domain/provider functions", "JSON/HTTP response"]
    if commands:
        return ["script invocation", "environment checks", "Python entrypoint", "project workflow", "filesystem/API side effects"]
    if summary.get("entrypoints"):
        return ["entrypoint invocation", "Python module execution", "result or side effect"]
    return ["not enough evidence"]


def _pipeline_candidate(summary: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    if routes:
        return ["validate request", "load config/state", "call handler/core logic", "handle errors", "return response"]
    if commands:
        return ["prepare environment", "read inputs", "transform/process", "write artifacts", "report status"]
    return ["scan inputs", "process", "emit output"]


def _capability_candidates(python_structure: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    pure = [item for item in python_structure.get("pure_transform_candidates", []) if is_core_path(str(item.get("path", "")))]
    candidates = [f"{item.get('path')}:{item.get('name')}" for item in pure[:8]]
    contracts = dict(python_structure.get("contracts", {}))
    schema_like = [item for item in contracts.get("schema_like_classes", []) if is_core_path(str(item.get("path", "")))]
    candidates.extend([f"{item.get('path')}:{item.get('name')}" for item in schema_like[:6]])
    if not schema_like:
        candidates.extend([f"{route.get('methods') or ['GET']} {route.get('route')}" for route in routes[:5]])
    return candidates[:15]


def _core_pure_transforms(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in python_structure.get("pure_transform_candidates", [])
        if is_core_path(str(item.get("path", "")))
    ][:12]


def _fallback_logic(python_structure: dict[str, Any], docs: str) -> list[str]:
    hints = []
    text = docs.lower()
    if "fallback" in text or "retry" in text or "degradation" in text:
        hints.append("Fallback/retry/degradation mentioned in docs.")
    for node in python_structure.get("central_nodes", []):
        name = str(node.get("name", "")).lower()
        if any(token in name for token in ("fallback", "retry", "recover", "handle")):
            hints.append(f"Function name suggests fallback/error handling: {node.get('path')}:{node.get('name')}")
    return hints[:8] or ["not enough evidence"]


def _data_structures(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    names = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("schema_like_classes", [])]
    typed = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("typed_functions", [])[:8]]
    return (names + typed)[:15] or ["not enough evidence"]


def _weak_contract_zones(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    return [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("untyped_functions", [])[:12]]


def _artifacts_to_persist(imports: set[str], stack: dict[str, Any]) -> list[str]:
    artifacts = ["raw input", "normalized/parsed output", "execution logs", "final report"]
    if imports & {"sqlite3", "sqlalchemy"}:
        artifacts.append("database checkpoints")
    if imports & {"requests", "httpx", "openai"}:
        artifacts.append("external API request/response cache")
    if stack.get("large_artifacts"):
        artifacts.append("large derived artifacts manifest")
    return artifacts


def _auto_contract_feasibility(python_structure: dict[str, Any]) -> str:
    contracts = dict(python_structure.get("contracts", {}))
    typed = len(contracts.get("typed_functions", []))
    untyped = len(contracts.get("untyped_functions", []))
    if typed >= untyped:
        return "good: type hints/schema-like classes provide enough seeds for generated contracts"
    if typed:
        return "partial: combine type hints with tests/docstrings to infer contracts"
    return "weak: many functions need explicit schemas or annotations first"


def _likely_error_types(risks: list[dict[str, str]], imports: set[str]) -> list[str]:
    errors = {"bad input", "runtime bug"}
    if imports & {"requests", "httpx", "openai"}:
        errors.update({"timeout", "external API failure"})
    if imports & {"subprocess"}:
        errors.add("dependency/process failure")
    if any(risk.get("code") == "unpinned_dependencies" for risk in risks):
        errors.add("dependency drift")
    return sorted(errors)


def _error_handling_hints(python_structure: dict[str, Any]) -> list[str]:
    hints = []
    for node in python_structure.get("central_nodes", []):
        if any(token in str(node.get("name", "")).lower() for token in ("handle", "error", "retry", "fallback")):
            hints.append(f"{node.get('path')}:{node.get('name')}")
    return hints or ["not enough evidence from static summary"]


def _state_to_preserve(imports: set[str], stack: dict[str, Any]) -> list[str]:
    state = ["input payload", "config snapshot", "code/plugin version", "execution log"]
    if imports & {"sqlite3", "sqlalchemy"}:
        state.append("database state or migration version")
    if stack.get("large_artifacts"):
        state.append("artifact manifest/checksums")
    return state


def _reproducibility(files: dict[str, Any], stack: dict[str, Any], commands: list[dict[str, Any]]) -> str:
    has_deps = bool(stack.get("dependency_files"))
    has_readme = any("readme" in str(item.get("path", "")).lower() for item in files.get("files", []))
    has_command = bool(commands)
    if has_deps and has_readme and has_command:
        return "moderate: dependencies, docs and runtime commands are discoverable; pinning/checkpoints still need audit"
    if has_deps:
        return "partial: dependency files exist, but runtime/docs evidence is incomplete"
    return "weak: reproducibility needs explicit dependencies, config and run instructions"


def _minimal_loop(routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    if routes:
        first = routes[0]
        return [
            f"call route {first.get('methods') or ['GET']} {first.get('route')}",
            "capture request/response",
            "simulate bad input or provider failure",
            "emit interrupt packet",
            "retry/switch/stop",
            "write final report",
        ]
    if commands:
        first = commands[0]
        return [
            f"run script {first.get('path')}",
            "capture stdout/stderr and artifacts",
            "simulate missing dependency or bad input",
            "emit interrupt packet",
            "retry/switch/stop",
            "write final report",
        ]
    return ["select entrypoint", "capture input/output", "inject controlled failure", "interrupt", "final report"]


def _representative_command(commands: list[str]) -> str:
    priority_markers = ("python", "pip install", "pytest", "npm ", "pnpm ", "yarn ", "uvicorn", "flask")
    for marker in priority_markers:
        for command in commands:
            lower = command.lower()
            if marker in lower and not lower.startswith(("if ", "echo ", "set ")):
                return command
    for command in commands:
        lower = command.lower()
        if not lower.startswith(("if ", "echo ", "set ")):
            return command
    return commands[0] if commands else ""

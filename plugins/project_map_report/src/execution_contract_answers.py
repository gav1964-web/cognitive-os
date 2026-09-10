"""Execution, capability, and contract answer helpers."""

from __future__ import annotations

from typing import Any

from .core_paths import is_core_path


def command_summary(command: dict[str, Any]) -> dict[str, str]:
    return {"path": str(command.get("path")), "purpose": str(command.get("purpose")), "command": _representative_command(command.get("commands") or [])}


def execution_path(
    summary: dict[str, Any],
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    domain_profile: dict[str, Any] | None = None,
) -> list[str]:
    if dict(domain_profile or {}).get("kind") == "llm_provider_gateway":
        return [
            "OpenAI-compatible HTTP request",
            "request/schema validation",
            "model/provider route resolution",
            "provider adapter call",
            "normalized OpenAI-compatible response or error",
        ]
    if dict(domain_profile or {}).get("kind") == "llm_auto_repair_loop":
        return [
            "template copy",
            "Docker build/run",
            "captured failure log",
            "LLM repair request",
            "validated file update package",
            "retry or save successful template",
        ]
    if routes:
        return ["HTTP request", "framework router", "route handler", "domain/provider functions", "JSON/HTTP response"]
    if commands:
        return ["script invocation", "environment checks", "Python entrypoint", "project workflow", "filesystem/API side effects"]
    if looks_like_python_library(summary):
        return ["user imports package/API", "public function or object method", "core library logic", "return value or controlled side effect"]
    if summary.get("entrypoints"):
        return ["entrypoint invocation", "Python module execution", "result or side effect"]
    return ["not enough evidence"]


def looks_like_python_library(summary: dict[str, Any]) -> bool:
    languages = {str(item).lower() for item in summary.get("languages", [])}
    if "python" not in languages:
        return False
    read_files = [str(item).lower().replace("\\", "/") for item in summary.get("read_files", [])]
    if not any(path in {"pyproject.toml", "setup.py", "setup.cfg"} for path in read_files):
        return False
    entrypoints = [str(item).lower().replace("\\", "/") for item in summary.get("entrypoints", []) if item]
    return not entrypoints or all(_is_package_surface_entrypoint(path) for path in entrypoints)


def _is_package_surface_entrypoint(path: str) -> bool:
    normalized = path.strip("/").lower()
    if normalized.endswith("/__init__.py") or normalized == "__init__.py":
        return True
    parts = normalized.split("/")
    if len(parts) >= 2 and parts[0] not in {"scripts", "tools", "examples", "tests", "test"}:
        return True
    return False


def pipeline_candidate(summary: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    if routes:
        return ["validate request", "load config/state", "call handler/core logic", "handle errors", "return response"]
    if commands:
        return ["prepare environment", "read inputs", "transform/process", "write artifacts", "report status"]
    return ["scan inputs", "process", "emit output"]


def capability_candidates(python_structure: dict[str, Any], routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
    pure = [item for item in python_structure.get("pure_transform_candidates", []) if is_core_path(str(item.get("path", "")))]
    candidates = [f"{item.get('path')}:{item.get('name')}" for item in pure[:8]]
    candidates.extend(_provider_parser_capabilities(python_structure))
    contracts = dict(python_structure.get("contracts", {}))
    schema_like = [
        item
        for item in contracts.get("schema_like_classes", [])
        if is_core_path(str(item.get("path", ""))) and not str(item.get("name", "")).endswith("Config")
    ]
    candidates.extend([f"{item.get('path')}:{item.get('name')}" for item in schema_like[:6]])
    if not schema_like:
        candidates.extend([f"{route.get('methods') or ['GET']} {route.get('route')}" for route in routes[:5]])
    return list(dict.fromkeys(candidates))[:24]


def fallback_logic(python_structure: dict[str, Any], docs: str) -> list[str]:
    hints = []
    text = docs.lower()
    if "fallback" in text or "retry" in text or "degradation" in text:
        hints.append("Fallback/retry/degradation mentioned in docs.")
    for node in python_structure.get("central_nodes", []):
        name = str(node.get("name", "")).lower()
        if any(token in name for token in ("fallback", "retry", "recover", "handle")):
            hints.append(f"Function name suggests fallback/error handling: {node.get('path')}:{node.get('name')}")
    return hints[:8] or ["not enough evidence"]


def data_structures(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    names = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("schema_like_classes", [])]
    typed = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("typed_functions", [])[:8]]
    return (names + typed)[:15] or ["not enough evidence"]


def weak_contract_zones(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    return [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("untyped_functions", [])[:12]]


def artifacts_to_persist(imports: set[str], stack: dict[str, Any]) -> list[str]:
    artifacts = ["raw input", "normalized/parsed output", "execution logs", "final report"]
    if imports & {"sqlite3", "sqlalchemy"}:
        artifacts.append("database checkpoints")
    if imports & {"requests", "httpx", "openai"}:
        artifacts.append("external API request/response cache")
    if stack.get("large_artifacts"):
        artifacts.append("large derived artifacts manifest")
    return artifacts


def auto_contract_feasibility(python_structure: dict[str, Any]) -> str:
    contracts = dict(python_structure.get("contracts", {}))
    typed = len(contracts.get("typed_functions", []))
    untyped = len(contracts.get("untyped_functions", []))
    if typed >= untyped:
        return "good: type hints/schema-like classes provide enough seeds for generated contracts"
    if typed:
        return "partial: combine type hints with tests/docstrings to infer contracts"
    return "weak: many functions need explicit schemas or annotations first"


def _provider_parser_capabilities(python_structure: dict[str, Any]) -> list[str]:
    markers = ("normalize", "parse", "extract", "curl_fallback", "fetch_available_models")
    raw_payload_helpers = ("extract_json_object", "_parse_llm_response", "parse_llm_response")
    rows = []
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "")
        normalized = path.replace("\\", "/").lower()
        if not is_core_path(path) or not normalized.endswith("_llm_client.py"):
            continue
        for function in file_row.get("functions", []):
            name = str(function.get("name") or "")
            if any(helper == name.lower() for helper in raw_payload_helpers):
                continue
            if any(marker in name.lower() for marker in markers):
                rows.append(f"{path}:{name}")
    return rows[:12]


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

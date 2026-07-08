"""Shared helpers for runtime extraction readiness heuristics."""

from __future__ import annotations

from typing import Any

from .core_paths import is_core_path


def unsafe_candidate_reason(function: dict[str, Any]) -> str:
    path = str(function.get("path") or "").replace("\\", "/").lower()
    name = str(function.get("name") or "").lower()
    dangerous_names = {"exec", "exec_", "eval", "compile", "run", "main"}
    api_boundary_names = {
        "request",
        "stream",
        "send",
        "serve",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "options",
        "head",
        "handle_request",
        "handle_async_request",
    }
    if len(name) <= 1:
        return "too_weak_symbol_name"
    if name in dangerous_names or name.startswith(("exec_", "eval_")):
        return "dangerous_runtime_helper"
    if path.endswith(("_api.py", "/api.py")) and name in api_boundary_names:
        return "api_boundary"
    return ""


def is_safe_extraction_candidate(function: dict[str, Any]) -> bool:
    return not unsafe_candidate_reason(function)


def data_structures(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    names = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("schema_like_classes", [])]
    typed = [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("typed_functions", [])[:8]]
    return (names + typed)[:15] or ["not enough evidence"]


def weak_contract_zones(python_structure: dict[str, Any]) -> list[str]:
    contracts = dict(python_structure.get("contracts", {}))
    return [f"{item.get('path')}:{item.get('name')}" for item in contracts.get("untyped_functions", [])[:12]]


def all_functions(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    return [function for file in python_structure.get("files", []) for function in file.get("functions", [])]


def boundary_function_candidates(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = ("load", "read", "fetch", "parse", "write", "save", "send", "handle")
    wrapper_tokens = ("dispatch", "loop", "pipeline", "scrape")
    rows = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        name = str(fn.get("name", "")).lower()
        if name.startswith("_"):
            continue
        effects = set(fn.get("side_effects", []))
        if any(token in name for token in wrapper_tokens):
            continue
        if effects <= {"memory_state"} and not any(token in name for token in tokens):
            continue
        if any(token in name for token in tokens) or (effects - {"filesystem_read", "memory_state"}):
            rows.append(fn)
    return sorted(rows, key=lambda item: (0 if item.get("side_effects") else 1, str(item.get("name"))))


def responsibilities(function: dict[str, Any]) -> list[str]:
    calls = " ".join(str(call).lower() for call in function.get("calls", []))
    effects = set(function.get("side_effects", []))
    profile = dict(function.get("error_profile", {}))
    responsibilities = []
    if effects & {"filesystem", "network", "database", "subprocess"} or any(token in calls for token in ("open", "read", "write", "request", "post", "get")):
        responsibilities.append("io")
    if int(function.get("call_count") or len(function.get("calls", []))) >= 8 or any(token in calls for token in ("if", "route", "dispatch", "select")):
        responsibilities.append("control_flow")
    if profile.get("has_try") or profile.get("raises") or profile.get("handlers"):
        responsibilities.append("error_handling")
    if any(token in calls for token in ("json", "format", "render", "response", "markdown")):
        responsibilities.append("formatting")
    if effects:
        responsibilities.append("state_or_side_effect")
    if int(function.get("loc") or 0) >= 80:
        responsibilities.append("large_logic_surface")
    return sorted(set(responsibilities))


def flow_steps(function: dict[str, Any], calls: list[str]) -> list[dict[str, str]]:
    lower_calls = " ".join(call.lower() for call in calls)
    steps = []
    if any(token in lower_calls for token in ("open", "read", "load", "input", "request", "json.load")):
        steps.append({"step": "read input", "function": str(function.get("name")), "evidence": "input/read call"})
    if any(token in lower_calls for token in ("parse", "normalize", "transform", "validate", "clean")):
        steps.append({"step": "transform", "function": str(function.get("name")), "evidence": "transform-like call"})
    if any(token in lower_calls for token in ("retry", "fallback", "handle", "except")):
        steps.append({"step": "recover", "function": str(function.get("name")), "evidence": "recovery-like call"})
    effects = set(function.get("side_effects", []))
    if effects or any(token in lower_calls for token in ("write", "save", "dump", "send", "post", "commit")):
        steps.append({"step": "write output", "function": str(function.get("name")), "evidence": ",".join(sorted(effects)) or "write-like call"})
    if not steps and calls:
        steps.append({"step": "call collaborators", "function": str(function.get("name")), "evidence": ",".join(calls[:5])})
    return steps


def flow_confidence(steps: list[dict[str, str]]) -> float:
    return min(0.9, 0.45 + len(steps) * 0.12)


def function_evidence(function: dict[str, Any], reasons: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "file": function.get("path"),
            "symbol": function.get("name"),
            "line": function.get("line"),
            "reason": reason,
        }
        for reason in reasons[:6]
    ]


def safe_node_id(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "_" for char in value.rsplit(":", 1)[-1]]
    return "".join(chars).strip("_") or "capability"

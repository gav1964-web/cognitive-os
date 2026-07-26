"""Error, state and reproducibility answer helpers."""

from __future__ import annotations

from typing import Any


def likely_error_types(risks: list[dict[str, str]], imports: set[str]) -> list[str]:
    errors = {"bad input", "runtime bug"}
    if imports & {"requests", "httpx", "openai"}:
        errors.update({"timeout", "external API failure"})
    if imports & {"subprocess"}:
        errors.add("dependency/process failure")
    if any(risk.get("code") == "unpinned_dependencies" for risk in risks):
        errors.add("dependency drift")
    return sorted(errors)


def error_handling_hints(python_structure: dict[str, Any]) -> list[str]:
    hints = []
    for node in python_structure.get("central_nodes", []):
        if any(token in str(node.get("name", "")).lower() for token in ("handle", "error", "retry", "fallback")):
            hints.append(f"{node.get('path')}:{node.get('name')}")
    return hints or ["not enough evidence from static summary"]


def state_to_preserve(imports: set[str], stack: dict[str, Any]) -> list[str]:
    state = ["input payload", "config snapshot", "code/plugin version", "execution log"]
    if imports & {"sqlite3", "sqlalchemy"}:
        state.append("database state or migration version")
    if stack.get("large_artifacts"):
        state.append("artifact manifest/checksums")
    return state


def reproducibility(files: dict[str, Any], stack: dict[str, Any], commands: list[dict[str, Any]]) -> str:
    has_deps = bool(stack.get("dependency_files"))
    has_readme = any("readme" in str(item.get("path", "")).lower() for item in files.get("files", []))
    has_command = bool(commands)
    if has_deps and has_readme and has_command:
        return "moderate: dependencies, docs and runtime commands are discoverable; pinning/checkpoints still need audit"
    if has_deps:
        return "partial: dependency files exist, but runtime/docs evidence is incomplete"
    return "weak: reproducibility needs explicit dependencies, config and run instructions"


def minimal_loop(routes: list[dict[str, Any]], commands: list[dict[str, Any]]) -> list[str]:
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

"""Build a compact project analysis report from project-analysis artifacts."""

from __future__ import annotations

from typing import Any

from .answers import build_answers, inline_value
from .core_paths import is_core_path
from .source_health import source_health as build_source_health


RISKY_IMPORTS = {"subprocess", "os", "threading"}


def run(payload: dict[str, object]) -> dict[str, object]:
    tree = dict(payload["tree"])  # type: ignore[index]
    stack = dict(payload["stack"])  # type: ignore[index]
    files = dict(payload["files"])  # type: ignore[index]
    python_structure = dict(payload["python_structure"])  # type: ignore[index]
    runtime_commands = dict(payload["runtime_commands"])  # type: ignore[index]
    source_health = build_source_health(tree, stack, files, python_structure, runtime_commands)
    security_health = _security_health(files)
    summary = {
        "root": tree.get("root"),
        "file_count": dict(tree.get("counts", {})).get("files", 0),
        "directory_count": dict(tree.get("counts", {})).get("directories", 0),
        "project_shape": source_health["project_shape"],
        "source_health_status": source_health["status"],
        "languages": [item.get("language") for item in stack.get("languages", [])[:6]],
        "frameworks": stack.get("frameworks", []),
        "entrypoints": _entrypoints(stack, python_structure),
        "routes": len(python_structure.get("routes", [])),
        "read_files": [item.get("path") for item in files.get("files", [])],
    }
    risks = _risks(tree, stack, files, python_structure, runtime_commands, source_health)
    answers = build_answers(summary, risks, stack, files, python_structure, runtime_commands)
    answers["0_source_health"] = source_health
    answers["0_security_health"] = security_health
    human_summary = _human_summary(summary, answers, source_health, security_health)
    evidence_summary = _evidence_summary(summary, answers, source_health, security_health, python_structure)
    markdown = _markdown(summary, risks, stack, python_structure, runtime_commands, answers, source_health, security_health, human_summary, evidence_summary)
    return {
        "summary": summary,
        "human_summary": human_summary,
        "evidence_summary": evidence_summary,
        "source_health": source_health,
        "security_health": security_health,
        "risks": risks,
        "answers": answers,
        "markdown": markdown,
    }


def _entrypoints(stack: dict[str, Any], python_structure: dict[str, Any]) -> list[str]:
    stack_entrypoints = [str(item) for item in stack.get("entrypoints", []) if item]
    if stack_entrypoints:
        return sorted(dict.fromkeys(stack_entrypoints))
    package_inits = []
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "")
        if not path.endswith("/__init__.py") or not is_core_path(path):
            continue
        parts = path.split("/")
        if parts[0] == "src" and len(parts) >= 3:
            package_inits.append(path)
        elif len(parts) == 2 and parts[0].replace("_", "").isalnum():
            package_inits.append(path)
    return sorted(package_inits)[:5]


def _risks(
    tree: dict[str, Any],
    stack: dict[str, Any],
    files: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
    source_health: dict[str, Any],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if source_health["status"] != "clean":
        risks.append(
            {
                "code": "source_health_not_clean",
                "severity": "high" if source_health["status"] == "damaged" else "medium",
                "detail": f"{source_health['status']} source tree; shape={source_health['project_shape']}",
            }
        )
    if source_health["project_shape"] == "dirty_portfolio":
        risks.append({"code": "dirty_portfolio_detected", "severity": "medium", "detail": "many projects/runs are mixed under one root"})
    if source_health.get("packaged_copy_signal_count"):
        risks.append(
            {
                "code": "packaged_copy_detected",
                "severity": "high",
                "detail": ", ".join(source_health.get("packaged_copy_samples", [])[:5]),
            }
        )
    if source_health.get("artifact_noise_signal_count"):
        risks.append(
            {
                "code": "artifact_noise_detected",
                "severity": "medium",
                "detail": ", ".join(source_health.get("artifact_noise_samples", [])[:5]),
            }
        )
    if source_health.get("env_file_signal_count"):
        risks.append(
            {
                "code": "env_file_in_project_tree",
                "severity": "high",
                "detail": ", ".join(source_health.get("env_file_samples", [])[:5]),
            }
        )
    if source_health["syntax_error_count"]:
        risks.append({"code": "python_syntax_errors", "severity": "high", "detail": f"{source_health['syntax_error_count']} Python files failed AST parsing"})
    if source_health["inaccessible_count"]:
        risks.append({"code": "inaccessible_paths", "severity": "medium", "detail": f"{source_health['inaccessible_count']} paths could not be accessed"})
    large = stack.get("large_artifacts", [])
    if large:
        risks.append({"code": "large_artifacts", "severity": "medium", "detail": f"{len(large)} large files"})
    imports = set(python_structure.get("imports", []))
    risky = sorted(imports & RISKY_IMPORTS)
    if risky:
        risks.append({"code": "risky_imports", "severity": "medium", "detail": ", ".join(risky)})
    secret_hits = _secret_hits(files)
    if secret_hits:
        risks.append({"code": "secret_material_in_source", "severity": "high", "detail": ", ".join(secret_hits[:5])})
    duplicated = any(str(item.get("path", "")).startswith("map_install_package/") for item in stack.get("dependency_files", []))
    if duplicated:
        risks.append({"code": "packaged_copy_detected", "severity": "low", "detail": "map_install_package duplicates source files"})
    dependencies = [dep for item in stack.get("dependency_files", []) for dep in item.get("dependencies", [])]
    if dependencies and not all("==" in dep for dep in dependencies):
        risks.append({"code": "unpinned_dependencies", "severity": "low", "detail": "requirements are not fully pinned"})
    if not runtime_commands.get("commands"):
        risks.append({"code": "no_runtime_scripts", "severity": "low", "detail": "no scripts detected"})
    if dict(tree.get("counts", {})).get("truncated"):
        risks.append({"code": "tree_scan_truncated", "severity": "medium", "detail": "tree scan hit limits"})
    return risks


def _secret_hits(files: dict[str, Any]) -> list[str]:
    markers = (
        "api_key",
        "client_secret",
        "access_token",
        "auth_token",
        "use_auth_token",
        "authorization",
        "bearer ",
        "hf_",
        "sk-",
    )
    hits = []
    for row in files.get("files", []):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").lower()
        path = str(row.get("path") or "")
        if any(marker in text for marker in markers):
            hits.append(path)
    return sorted(dict.fromkeys(hits))


def _security_health(files: dict[str, Any]) -> dict[str, Any]:
    hits = _secret_hits(files)
    if hits:
        status = "attention_required"
        recommendation = "move secrets to environment or secret storage; redact before reports, logs, and replay artifacts"
    else:
        status = "clean"
        recommendation = "no obvious secret markers found in sampled text files"
    return {
        "status": status,
        "secret_hit_count": len(hits),
        "secret_hit_samples": hits[:12],
        "recommendation": recommendation,
    }


def _human_summary(
    summary: dict[str, Any],
    answers: dict[str, Any],
    source_health: dict[str, Any],
    security_health: dict[str, Any],
) -> dict[str, Any]:
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    scenarios = list(scope.get("supported_scenarios", []) or [])
    if not scenarios:
        path = list(execution.get("primary_execution_path", []) or [])
        if path:
            scenarios = [f"Execute primary flow: {' -> '.join(str(item) for item in path[:4])}"]
        elif summary.get("entrypoints"):
            scenarios = [f"Run detected entrypoint `{summary['entrypoints'][0]}` and inspect produced outputs."]
    next_step = "write ArchitectureDecisionRecord for the safest source-backed capability"
    if plan.get("blocked_by"):
        next_step = "stop implementation handoff until Project Analyzer has a safe Python candidate"
    return {
        "purpose": scope.get("main_task") or f"Analyze project at {summary.get('root')} and identify its runtime boundaries.",
        "main_scenarios": scenarios[:5],
        "inputs": list(scope.get("inputs", []) or [])[:8],
        "outputs": list(scope.get("outputs", []) or [])[:8],
        "recommended_next_step": next_step,
        "source_health": source_health.get("status"),
        "security_health": security_health.get("status"),
    }


def _evidence_summary(
    summary: dict[str, Any],
    answers: dict[str, Any],
    source_health: dict[str, Any],
    security_health: dict[str, Any],
    python_structure: dict[str, Any],
) -> dict[str, Any]:
    execution = dict(answers.get("2_execution", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    refs = [
        "ProjectMapReport.summary",
        "ProjectMapReport.answers.1_scope",
        "ProjectMapReport.answers.2_execution",
        "ProjectMapReport.answers.6_runtime_extraction_readiness",
    ]
    refs.extend(str(item) for item in list(execution.get("entrypoints", []))[:4] if item)
    refs.extend(
        f"{row.get('path')}:{row.get('name')}"
        for row in list(readiness.get("hidden_orchestrators", []))[:4]
        if isinstance(row, dict) and row.get("path") and row.get("name")
    )
    confidence = 0.9
    if source_health.get("status") != "clean":
        confidence -= 0.15
    if security_health.get("status") != "clean":
        confidence -= 0.1
    if not python_structure.get("files"):
        confidence -= 0.2
    return {
        "source_refs": sorted(dict.fromkeys(refs)),
        "confidence": round(max(0.2, confidence), 2),
        "limits": [
            "static analysis cannot prove dynamically imported entrypoints",
            "absence of evidence is not evidence of absence for generated/runtime code",
        ],
    }


def _markdown(
    summary: dict[str, Any],
    risks: list[dict[str, str]],
    stack: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
    answers: dict[str, Any],
    source_health: dict[str, Any],
    security_health: dict[str, Any],
    human_summary: dict[str, Any],
    evidence_summary: dict[str, Any],
) -> str:
    lines = [
        "# Project Map Report",
        "",
        f"Root: `{summary['root']}`",
        f"Files: `{summary['file_count']}`, directories: `{summary['directory_count']}`",
        f"Project shape: `{source_health['project_shape']}`, source health: `{source_health['status']}`",
        f"Frameworks: {', '.join(summary['frameworks']) or 'none detected'}",
        f"Entrypoints: {', '.join(summary['entrypoints']) or 'none detected'}",
        "",
        "## Human Summary",
        f"- Purpose: {human_summary.get('purpose')}",
        f"- Main scenarios: {inline_value(human_summary.get('main_scenarios'))}",
        f"- Recommended next step: {human_summary.get('recommended_next_step')}",
        "",
        "## Evidence Summary",
        f"- Confidence: `{evidence_summary.get('confidence')}`",
        f"- Source refs: {inline_value(evidence_summary.get('source_refs'))}",
        f"- Limits: {inline_value(evidence_summary.get('limits'))}",
        "",
        "## Source Health",
        f"- Status: `{source_health['status']}`",
        f"- Shape: `{source_health['project_shape']}`",
        f"- Syntax errors: `{source_health['syntax_error_count']}`",
        f"- Inaccessible/skipped paths: `{source_health['inaccessible_count']}`",
        f"- Generated/duplicated run signals: `{source_health['generated_run_signal_count']}`",
        f"- Recommendation: {source_health['recommendation']}",
        "",
        "## Security Health",
        f"- Status: `{security_health['status']}`",
        f"- Secret marker hits: `{security_health['secret_hit_count']}`",
        f"- Samples: {', '.join(security_health['secret_hit_samples']) or 'none'}",
        f"- Recommendation: {security_health['recommendation']}",
        "",
        "## Runtime Commands",
    ]
    for command in _active_runtime_commands(runtime_commands)[:10]:
        first = _representative_command(command.get("commands") or [])
        lines.append(f"- `{command.get('path')}`: {command.get('purpose')} -> `{first}`")
    lines.extend(["", "## Routes"])
    for route in python_structure.get("routes", [])[:20]:
        methods = ",".join(route.get("methods") or ["GET"])
        lines.append(f"- `{methods}` `{route.get('route')}` -> `{route.get('path')}:{route.get('function')}`")
    lines.extend(["", "## Large Artifacts"])
    for artifact in stack.get("large_artifacts", [])[:10]:
        lines.append(f"- `{artifact.get('path')}`: {artifact.get('size_bytes')} bytes")
    lines.extend(["", "## Risks"])
    for risk in risks:
        lines.append(f"- `{risk['severity']}` `{risk['code']}`: {risk['detail']}")
    lines.extend(["", "## Analysis Answers", ""])
    for section_name, section in answers.items():
        lines.append(f"### {section_name}")
        for key, value in section.items():
            lines.append(f"- **{key}**: {inline_value(value)}")
        lines.append("")
    return "\n".join(lines) + "\n"


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


def _active_runtime_commands(runtime_commands: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        command
        for command in runtime_commands.get("commands", [])
        if isinstance(command, dict) and is_core_path(str(command.get("path", "")))
    ]

"""Build a compact project analysis report from project-analysis artifacts."""

from __future__ import annotations

from typing import Any

from .answers import build_answers, inline_value
from .core_paths import is_core_path


RISKY_IMPORTS = {"subprocess", "os", "threading"}


def run(payload: dict[str, object]) -> dict[str, object]:
    tree = dict(payload["tree"])  # type: ignore[index]
    stack = dict(payload["stack"])  # type: ignore[index]
    files = dict(payload["files"])  # type: ignore[index]
    python_structure = dict(payload["python_structure"])  # type: ignore[index]
    runtime_commands = dict(payload["runtime_commands"])  # type: ignore[index]
    source_health = _source_health(tree, stack, files, python_structure, runtime_commands)
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
    markdown = _markdown(summary, risks, stack, python_structure, runtime_commands, answers, source_health, security_health)
    return {
        "summary": summary,
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


def _markdown(
    summary: dict[str, Any],
    risks: list[dict[str, str]],
    stack: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
    answers: dict[str, Any],
    source_health: dict[str, Any],
    security_health: dict[str, Any],
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


def _source_health(
    tree: dict[str, Any],
    stack: dict[str, Any],
    files: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
) -> dict[str, Any]:
    tree_skipped = dict(tree.get("skipped", {}))
    py_skipped = [row for row in python_structure.get("skipped", []) if isinstance(row, dict)]
    file_skipped = [row for row in files.get("skipped", []) if isinstance(row, dict)]
    runtime_skipped = [row for row in runtime_commands.get("skipped", []) if isinstance(row, dict)]
    syntax_errors = [row for row in py_skipped if str(row.get("reason")) == "SyntaxError"]
    inaccessible = [
        row
        for row in [*py_skipped, *file_skipped, *runtime_skipped]
        if str(row.get("reason")) not in {"SyntaxError", "too_large", "max_files_exceeded", "non_text_extension"}
    ]
    inaccessible_count = (
        int(tree_skipped.get("inaccessible_files") or 0)
        + int(tree_skipped.get("inaccessible_directories") or 0)
        + len(inaccessible)
    )
    entrypoints = [str(item) for item in stack.get("entrypoints", []) if item]
    dependency_files = [str(item.get("path", "")) for item in stack.get("dependency_files", []) if isinstance(item, dict)]
    generated_signals = _generated_run_signals(tree, stack, python_structure)
    packaged_copy_signals = _packaged_copy_signals(tree, stack, python_structure)
    artifact_noise_signals = _artifact_noise_signals(tree)
    env_file_signals = _env_file_signals(tree, files)
    project_shape = _project_shape(tree, entrypoints, dependency_files, generated_signals, packaged_copy_signals)
    status = "clean"
    if syntax_errors or inaccessible_count:
        status = "damaged"
    elif project_shape in {"dirty_portfolio", "multi_project_workspace"} or generated_signals or packaged_copy_signals or artifact_noise_signals or env_file_signals:
        status = "noisy"
    blockers = []
    if syntax_errors:
        blockers.append("repair or quarantine files that fail Python AST parsing")
    if inaccessible_count:
        blockers.append("skip or isolate inaccessible filesystem entries")
    if project_shape == "dirty_portfolio":
        blockers.append("choose a concrete project root before architecture extraction")
    if packaged_copy_signals:
        blockers.append("exclude nested packaged/snapshot copies from active source selection")
    if artifact_noise_signals:
        blockers.append("exclude logs, archives, caches, and generated artifacts before scoring architecture quality")
    if env_file_signals:
        blockers.append("treat .env files as configuration/security evidence, not active source")
    recommendation = "source tree is ready for normal project analysis"
    if blockers:
        recommendation = "; ".join(blockers)
    return {
        "status": status,
        "project_shape": project_shape,
        "syntax_error_count": len(syntax_errors),
        "syntax_error_samples": syntax_errors[:12],
        "inaccessible_count": inaccessible_count,
        "inaccessible_samples": inaccessible[:12],
        "generated_run_signal_count": len(generated_signals),
        "generated_run_samples": generated_signals[:12],
        "packaged_copy_signal_count": len(packaged_copy_signals),
        "packaged_copy_samples": packaged_copy_signals[:12],
        "artifact_noise_signal_count": len(artifact_noise_signals),
        "artifact_noise_samples": artifact_noise_signals[:12],
        "env_file_signal_count": len(env_file_signals),
        "env_file_samples": env_file_signals[:12],
        "entrypoint_count": len(entrypoints),
        "dependency_file_count": len(dependency_files),
        "tree_truncated": bool(dict(tree.get("counts", {})).get("truncated")),
        "recommendation": recommendation,
    }


def _project_shape(
    tree: dict[str, Any],
    entrypoints: list[str],
    dependency_files: list[str],
    generated_signals: list[str],
    packaged_copy_signals: list[str],
) -> str:
    counts = dict(tree.get("counts", {}))
    directories = int(counts.get("directories") or 0)
    files = int(counts.get("files") or 0)
    if packaged_copy_signals:
        return "dirty_portfolio"
    if directories >= 500 or len(entrypoints) >= 20 or len(dependency_files) >= 20 or len(generated_signals) >= 20:
        return "dirty_portfolio"
    if directories >= 80 or len(entrypoints) >= 8 or len(dependency_files) >= 8 or len(generated_signals) >= 8:
        return "multi_project_workspace"
    if files == 0:
        return "empty_or_unreadable"
    return "single_project"


def _generated_run_signals(
    tree: dict[str, Any],
    stack: dict[str, Any],
    python_structure: dict[str, Any],
) -> list[str]:
    paths: list[str] = []
    for row in tree.get("files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    for row in stack.get("dependency_files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    for row in python_structure.get("files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    signals = []
    for path in paths:
        lowered = path.replace("\\", "/").lower()
        if any(token in lowered for token in ("/runs/", "/generated/", "/scratch/", "/build/", "/dist/", "test_workspace/", "source_project/")):
            signals.append(path)
    return sorted(dict.fromkeys(signals))


def _packaged_copy_signals(
    tree: dict[str, Any],
    stack: dict[str, Any],
    python_structure: dict[str, Any],
) -> list[str]:
    paths: list[str] = []
    for row in tree.get("files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    for row in tree.get("directories", []):
        paths.append(str(row))
    for row in stack.get("dependency_files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    for row in python_structure.get("files", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path") or ""))
    signals = []
    for path in paths:
        lowered = path.replace("\\", "/").lower()
        parts = [part for part in lowered.split("/") if part]
        if len(parts) >= 2 and _looks_like_snapshot_dir(parts[0]):
            signals.append(path)
        if any(part.endswith(("_install_package", "_package")) for part in parts[:-1]):
            signals.append(path)
    return sorted(dict.fromkeys(signals))


def _artifact_noise_signals(tree: dict[str, Any]) -> list[str]:
    signals = []
    for row in tree.get("files", []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        lowered = path.replace("\\", "/").lower()
        if lowered.endswith((".zip", ".tar", ".tar.gz", ".tgz", ".log", ".jsonl", ".sqlite", ".db", ".pkl", ".pickle", ".bin", ".pt", ".pth", ".ipynb")):
            signals.append(path)
        elif "/.ipynb_checkpoints/" in f"/{lowered}":
            signals.append(path)
    return sorted(dict.fromkeys(signals))


def _env_file_signals(tree: dict[str, Any], files: dict[str, Any]) -> list[str]:
    signals = []
    for source in (tree.get("files", []), files.get("files", [])):
        for row in source:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "")
            if path.replace("\\", "/").lower().endswith(".env"):
                signals.append(path)
    return sorted(dict.fromkeys(signals))


def _looks_like_snapshot_dir(part: str) -> bool:
    lowered = part.lower()
    chunks = lowered.replace("-", "_").split("_")
    return any(len(chunk) == 8 and chunk.isdigit() and chunk.startswith(("20", "19")) for chunk in chunks)

"""Source tree health heuristics for project map reports."""

from __future__ import annotations

from typing import Any


def source_health(
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
    parser_incompatibilities = [
        row for row in py_skipped if str(row.get("reason")) == "ParserVersionIncompatible"
    ]
    parser_incompatibilities.extend(
        {
            "path": str(row.get("path") or ""),
            "reason": "ParserVersionIncompatible",
            "compatibility_mode": str(row.get("parser_compatibility") or ""),
        }
        for row in python_structure.get("files", [])
        if isinstance(row, dict) and row.get("parser_compatibility")
    )
    inaccessible = [
        row
        for row in [*py_skipped, *file_skipped, *runtime_skipped]
        if str(row.get("reason"))
        not in {"SyntaxError", "ParserVersionIncompatible", "too_large", "max_files_exceeded", "non_text_extension"}
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
    noise_exclusion_decision = _noise_exclusion_decision(
        generated_signals=generated_signals,
        artifact_noise_signals=artifact_noise_signals,
        env_file_signals=env_file_signals,
        project_shape=project_shape,
    )
    status = "clean"
    if syntax_errors or inaccessible_count:
        status = "damaged"
    elif parser_incompatibilities or project_shape in {"dirty_portfolio", "multi_project_workspace"} or generated_signals or packaged_copy_signals or artifact_noise_signals or env_file_signals:
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
        "parser_incompatibility_count": len(parser_incompatibilities),
        "parser_incompatibility_samples": parser_incompatibilities[:12],
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
        "noise_exclusion_decision": noise_exclusion_decision,
    }


def _noise_exclusion_decision(
    *,
    generated_signals: list[str],
    artifact_noise_signals: list[str],
    env_file_signals: list[str],
    project_shape: str,
) -> dict[str, Any]:
    signals = [*generated_signals, *artifact_noise_signals, *env_file_signals]
    if not signals:
        return {}
    if project_shape == "dirty_portfolio":
        return {
            "status": "pending_active_root",
            "policy": "noise is detected but downstream roles must wait for active-root selection before treating exclusions as safe",
            "excluded_signal_count": len(signals),
            "sample_paths": signals[:12],
        }
    return {
        "status": "context_only_noise_excluded",
        "policy": "logs, archives, notebooks, env files, caches, generated runs and build artifacts are evidence/context only and cannot become first-slice source targets",
        "excluded_signal_count": len(signals),
        "sample_paths": signals[:12],
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
        parts = [part for part in lowered.split("/") if part]
        artifact_dir = any(part in {"runs", "generated", "scratch", "dist"} for part in parts)
        artifact_dir = artifact_dir or _generated_build_artifact_path(parts)
        if artifact_dir or any(token in lowered for token in ("test_workspace/", "source_project/")):
            signals.append(path)
    return sorted(dict.fromkeys(signals))


def _generated_build_artifact_path(parts: list[str]) -> bool:
    if "build" not in parts:
        return False
    index = parts.index("build")
    if index == 0:
        return True
    if index > 0 and parts[index - 1] in {"src", "lib", "app", "apps"}:
        return False
    return True


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

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
    summary = {
        "root": tree.get("root"),
        "file_count": dict(tree.get("counts", {})).get("files", 0),
        "directory_count": dict(tree.get("counts", {})).get("directories", 0),
        "languages": [item.get("language") for item in stack.get("languages", [])[:6]],
        "frameworks": stack.get("frameworks", []),
        "entrypoints": _entrypoints(stack, python_structure),
        "routes": len(python_structure.get("routes", [])),
        "read_files": [item.get("path") for item in files.get("files", [])],
    }
    risks = _risks(tree, stack, python_structure, runtime_commands)
    answers = build_answers(summary, risks, stack, files, python_structure, runtime_commands)
    markdown = _markdown(summary, risks, stack, python_structure, runtime_commands, answers)
    return {"summary": summary, "risks": risks, "answers": answers, "markdown": markdown}


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
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    large = stack.get("large_artifacts", [])
    if large:
        risks.append({"code": "large_artifacts", "severity": "medium", "detail": f"{len(large)} large files"})
    imports = set(python_structure.get("imports", []))
    risky = sorted(imports & RISKY_IMPORTS)
    if risky:
        risks.append({"code": "risky_imports", "severity": "medium", "detail": ", ".join(risky)})
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


def _markdown(
    summary: dict[str, Any],
    risks: list[dict[str, str]],
    stack: dict[str, Any],
    python_structure: dict[str, Any],
    runtime_commands: dict[str, Any],
    answers: dict[str, Any],
) -> str:
    lines = [
        "# Project Map Report",
        "",
        f"Root: `{summary['root']}`",
        f"Files: `{summary['file_count']}`, directories: `{summary['directory_count']}`",
        f"Frameworks: {', '.join(summary['frameworks']) or 'none detected'}",
        f"Entrypoints: {', '.join(summary['entrypoints']) or 'none detected'}",
        "",
        "## Runtime Commands",
    ]
    for command in runtime_commands.get("commands", [])[:10]:
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

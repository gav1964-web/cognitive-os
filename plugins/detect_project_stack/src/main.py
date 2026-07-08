"""Detect project stack signals from filenames and small dependency files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "venv"}
LANGUAGE_BY_EXTENSION = {
    ".bat": "Batch",
    ".css": "CSS",
    ".html": "HTML",
    ".js": "JavaScript",
    ".json": "JSON",
    ".md": "Markdown",
    ".py": "Python",
    ".rtf": "RTF",
    ".xlsx": "Excel",
}
DEPENDENCY_FILES = {"requirements.txt", "pyproject.toml", "package.json", "setup.py"}
ENTRYPOINT_NAMES = {"app.py", "main.py", "server.py", "manage.py"}
LARGE_ARTIFACT_BYTES = 50 * 1024 * 1024


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_path(str(payload["path"]))
    extension_counts: dict[str, int] = {}
    dependency_files: list[dict[str, Any]] = []
    entrypoints: list[str] = []
    scripts: list[str] = []
    large_artifacts: list[dict[str, Any]] = []
    dependency_text = ""
    framework_text = ""

    for item in _iter_project_files(root):
        rel_path = item.relative_to(root).as_posix()
        suffix = item.suffix.lower()
        if suffix:
            extension_counts[suffix] = extension_counts.get(suffix, 0) + 1
        lower_name = item.name.lower()
        size = item.stat().st_size
        if lower_name in DEPENDENCY_FILES:
            content = _read_small_text(item)
            dependency_text += "\n" + content.lower()
            if not _is_context_path(rel_path):
                framework_text += "\n" + content.lower()
            dependency_files.append({"path": rel_path, "size_bytes": size, "dependencies": _dependency_names(content)})
        if (lower_name in ENTRYPOINT_NAMES or lower_name.startswith(("run_", "start_"))) and not _is_context_path(rel_path):
            entrypoints.append(rel_path)
        if suffix in {".bat", ".sh", ".ps1"}:
            scripts.append(rel_path)
        if size >= LARGE_ARTIFACT_BYTES:
            large_artifacts.append({"path": rel_path, "size_bytes": size, "extension": suffix or "<none>"})

    languages = [
        {"language": LANGUAGE_BY_EXTENSION.get(extension, extension), "files": count}
        for extension, count in sorted(extension_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "root": root.as_posix(),
        "languages": languages,
        "frameworks": _frameworks(framework_text, entrypoints),
        "dependency_files": sorted(dependency_files, key=lambda item: item["path"]),
        "entrypoints": sorted(entrypoints),
        "scripts": sorted(scripts),
        "large_artifacts": sorted(large_artifacts, key=lambda item: item["size_bytes"], reverse=True),
    }


def _iter_project_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        for item in sorted(current.iterdir(), key=lambda path: path.name.lower()):
            if item.is_dir():
                if item.name in EXCLUDED_DIRS or item.name.startswith(".") or item.name.lower().endswith("_install_package"):
                    continue
                stack.append(item)
            elif item.is_file():
                yield item


def _dependency_names(content: str) -> list[str]:
    names = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for separator in ("==", ">=", "<=", "~=", ">", "<", "="):
            if separator in line:
                line = line.split(separator, 1)[0].strip()
                break
        names.append(line)
    return names[:50]


def _frameworks(dependency_text: str, entrypoints: list[str]) -> list[str]:
    frameworks = []
    if "flask" in dependency_text or any(path.endswith("app.py") for path in entrypoints):
        frameworks.append("Flask-like Python web app")
    if "fastapi" in dependency_text:
        frameworks.append("FastAPI")
    if "folium" in dependency_text or "leaflet" in dependency_text:
        frameworks.append("Map/Leaflet visualization")
    return frameworks


def _is_context_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    parts = lowered.split("/")
    name = parts[-1] if parts else lowered
    if any(
        part in {"bench", "benchmarks", "ci_tools", "docs", "downstream", "examples", "failures-to-investigate", "integration", "scripts", "tasks", "test", "tests", "tools"}
        for part in parts
    ):
        return True
    if parts[:2] == ["packaging", "pep517_backend"]:
        return True
    return name in {"benchmark.py", "conftest.py", "noxfile.py"} or name.startswith("test_") or name.endswith("_test.py")


def _read_small_text(path: Path) -> str:
    if path.stat().st_size > 200_000:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _resolve_scoped_path(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("detect_project_stack path must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("detect_project_stack path is outside the allowed project scope")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

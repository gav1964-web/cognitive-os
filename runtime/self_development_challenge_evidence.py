"""Extract bounded project identity evidence for challenge selection."""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 runtime
    import tomli as tomllib


def bounded_project_text(project: Path) -> str:
    names, chunks, total = [], [], 0
    skipped = {
        ".git", ".hg", ".mypy_cache", ".pytest_cache", ".tox", ".venv",
        "venv", "node_modules", "__pycache__",
    }
    for current, dirs, files in os.walk(project):
        dirs[:] = sorted(
            name for name in dirs if name not in skipped and not name.startswith(".")
        )
        for filename in sorted(files):
            path = Path(current) / filename
            relative = path.relative_to(project).as_posix().lower()
            if path.suffix.lower() == ".py" and len(names) < 64:
                names.append(relative)
            if filename.lower() not in {
                "pyproject.toml", "setup.cfg", "setup.py", "readme.md", "readme.rst",
            }:
                continue
            try:
                value = path.read_text(encoding="utf-8", errors="replace")[:8192].lower()
            except OSError:
                continue
            chunks.append(value)
            total += len(value)
            if total >= 32768:
                break
        if total >= 32768:
            break
    return "\n".join([project.name.lower(), *names[:64], *chunks])


def declared_script_entrypoints(project: Path) -> list[str]:
    path = project / "pyproject.toml"
    if not path.is_file():
        return []
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, ValueError):
        return []
    project_scripts = dict(dict(payload.get("project") or {}).get("scripts") or {})
    poetry_scripts = dict(
        dict(dict(payload.get("tool") or {}).get("poetry") or {}).get("scripts") or {}
    )
    return [
        f"{name}={target}"
        for name, target in sorted({**poetry_scripts, **project_scripts}.items())
        if isinstance(target, str) and target.strip()
    ][:40]


def native_test_roots(project: Path) -> list[str]:
    roots = [name for name in ("tests", "test") if (project / name).is_dir()]
    roots.extend(
        path.name
        for path in sorted(project.glob("test*.py"))
        if path.is_file()
    )
    return sorted(dict.fromkeys(roots))[:20]


def signal_score(text: str, signals: list[str]) -> int:
    return sum(signal.lower() in text for signal in signals)


def name_signal_matches(name: str, signal: str) -> bool:
    return re.search(
        rf"(?:^|[^a-z0-9]){re.escape(signal.lower())}(?:$|[^a-z0-9])",
        name.lower(),
    ) is not None


def exposed_projects(root: Path, pattern: str) -> set[str]:
    """Collect project identities from single-project and batch JSON reports."""
    projects = set()
    for path in root.glob(pattern):
        try:
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = [payload, *(
            row for row in payload.get("cases") or [] if isinstance(row, dict)
        )]
        projects.update(
            project for row in rows
            if (project := str(row.get("project") or "").lower())
        )
    return projects

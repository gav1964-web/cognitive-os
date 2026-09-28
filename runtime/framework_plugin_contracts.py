"""Structural project-owned framework and plugin contract detection."""

from __future__ import annotations

import ast
import configparser
import hashlib
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 runtime
    import tomli as tomllib


def owned_contracts(project: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    contracts = []
    groups = _manifest_entrypoint_groups(project)
    matched_groups = sorted(groups.intersection(policy["plugin_entrypoint_groups"]))
    if matched_groups:
        contracts.append({"kind": "declared_plugin_entrypoint", "groups": matched_groups})
    required = set(policy["owned_backend_required_functions"])
    found, sources = (set(), set())
    if _declares_owned_backend(project):
        found, sources = _source_functions(project, set(policy["skip_directories"]))
    if required.issubset(found):
        contracts.append({
            "kind": "owned_packaging_build_backend",
            "required_functions": sorted(required),
            "sources": sorted(sources),
        })
    return contracts


def git_head(project: Path) -> str:
    head = project / ".git" / "HEAD"
    try:
        value = head.read_text(encoding="ascii").strip()
        if not value.startswith("ref: "):
            return value
        reference = project / ".git" / value[5:]
        if reference.is_file():
            return reference.read_text(encoding="ascii").strip()
        packed = (project / ".git" / "packed-refs").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return ""
    suffix = " " + value[5:]
    return next(
        (line.split(" ", 1)[0] for line in packed.splitlines() if line.endswith(suffix)),
        "",
    )


def source_fingerprint(project: Path, policy: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    skip = {str(value).lower() for value in policy["skip_directories"]}
    for current, dirs, files in os.walk(project):
        dirs[:] = sorted(name for name in dirs if name.lower() not in skip)
        for name in sorted(files):
            path = Path(current) / name
            relative = path.relative_to(project).as_posix()
            try:
                digest.update(relative.encode("utf-8") + b"\0" + path.read_bytes())
            except OSError:
                continue
    return digest.hexdigest()


def _manifest_entrypoint_groups(project: Path) -> set[str]:
    entries: dict[str, list[str]] = {}
    pyproject = project / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            declared = dict(dict(data.get("project") or {}).get("entry-points") or {})
            poetry = dict(dict(data.get("tool") or {}).get("poetry") or {})
            declared.update(dict(poetry.get("plugins") or {}))
            for group, values in declared.items():
                entries.setdefault(str(group), []).extend(_entrypoint_values(values))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            pass
    setup_cfg = project / "setup.cfg"
    if setup_cfg.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(setup_cfg, encoding="utf-8")
            if parser.has_section("options.entry_points"):
                for group, value in parser.items("options.entry_points"):
                    entries.setdefault(group, []).extend(
                        line.split("=", 1)[-1].strip()
                        for line in value.splitlines()
                        if line.strip()
                    )
        except (OSError, UnicodeError, configparser.Error):
            pass
    for group, values in _setup_py_entrypoints(project / "setup.py").items():
        entries.setdefault(group, []).extend(values)
    return {
        group
        for group, values in entries.items()
        if any(_entrypoint_target_is_owned(project, value) for value in values)
    }


def _declares_owned_backend(project: Path) -> bool:
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return False
    backend = str(dict(data.get("build-system") or {}).get("build-backend") or "")
    module = backend.split(":", 1)[0].strip().replace(".", "/")
    return bool(module) and (
        (project / f"{module}.py").is_file() or (project / module).is_dir()
    )


def _setup_py_entrypoints(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return {}
    groups: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "entry_points":
                continue
            try:
                value = ast.literal_eval(keyword.value)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict):
                for key, entries in value.items():
                    groups.setdefault(str(key), []).extend(_entrypoint_values(entries))
    return groups


def _entrypoint_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(item) for item in value.values()]
    if isinstance(value, (list, tuple)):
        return [str(item).split("=", 1)[-1].strip() for item in value]
    return [str(value)] if value else []


def _entrypoint_target_is_owned(project: Path, value: str) -> bool:
    module = value.split(":", 1)[0].strip().replace(".", "/")
    if not module:
        return False
    candidates = (
        project / f"{module}.py",
        project / module / "__init__.py",
        project / "src" / f"{module}.py",
        project / "src" / module / "__init__.py",
    )
    return any(path.is_file() for path in candidates)


def _source_functions(project: Path, skip: set[str]) -> tuple[set[str], set[str]]:
    found, sources = set(), set()
    for current, dirs, files in os.walk(project):
        dirs[:] = [name for name in dirs if name.lower() not in skip]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = Path(current) / name
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError):
                continue
            names = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if names:
                found.update(names)
                sources.add(path.relative_to(project).as_posix())
    return found, sources

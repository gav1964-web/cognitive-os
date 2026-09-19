"""Bounded, source-backed admission of Python library candidates (not proof of purity)."""
from __future__ import annotations

import ast
import configparser
import hashlib
import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from cognitive_replay.setup_identity import setup_py_distribution_name
from cognitive_replay.evidence import evidence_digest

IGNORED = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__",
           "build", "dist", "docs", "doc", "examples", "vendor", "vendored"}
APPLICATION_IMPORTS = {"django", "fastapi", "flask", "streamlit", "tkinter", "PyQt5", "PyQt6"}
IO_CALLS = {"open", "print", "input", "read_text", "read_bytes", "write_text", "write_bytes",
            "request", "getenv", "system", "popen", "connect", "send", "recv", "sleep"}


def _read(root: Path, relative: str, digests: dict) -> str:
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 300_000:
        raise ValueError(f"unreadable_or_unbounded:{relative}")
    raw = path.read_bytes()
    digests[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
    return raw.decode("utf-8-sig")


def package_identity(root: Path, digests: dict) -> dict:
    if (root / "pyproject.toml").is_file():
        payload = tomllib.loads(_read(root, "pyproject.toml", digests))
        project = payload.get("project") or payload.get("tool", {}).get("poetry") or {}
        if project.get("name"):
            return {"name": str(project["name"]), "manifest": "pyproject.toml"}
    if (root / "setup.cfg").is_file():
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(_read(root, "setup.cfg", digests))
        if parser.get("metadata", "name", fallback=""):
            return {"name": parser.get("metadata", "name"), "manifest": "setup.cfg"}
    if (root / "setup.py").is_file():
        _read(root, "setup.py", digests)
        name = setup_py_distribution_name(root)
        if name:
            return {"name": name, "manifest": "setup.py"}
    return {}


def _paths(root: Path) -> tuple[list[str], bool]:
    paths, visited = [], 0
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in IGNORED
                                and not name.startswith(".") and not (Path(current) / name).is_symlink())
        visited += len(directories) + len(files)
        if visited > 5000:
            return paths, True
        for name in sorted(files):
            path = Path(current) / name
            if path.suffix == ".py" and not path.is_symlink():
                paths.append(path.relative_to(root).as_posix())
                if len(paths) > 256:
                    return paths[:256], True
    return paths, False


def _is_test(relative: str) -> bool:
    path = Path(relative)
    return bool({"test", "tests"} & set(path.parts)) or path.name.startswith("test_") or path.name.endswith("_test.py")


def _module(relative: str) -> str:
    parts = list(Path(relative).with_suffix("").parts)
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _api(tree: ast.AST, module: str, relative: str) -> list[dict]:
    result = []
    for node in getattr(tree, "body", []):
        definitions = [(node, node.name)] if isinstance(node, ast.FunctionDef) else []
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            definitions = [(child, node.name + "." + child.name) for child in node.body
                           if isinstance(child, ast.FunctionDef) and not child.name.startswith("_")]
        for function, name in definitions:
            if name.startswith("_") or not (function.args.args or function.args.kwonlyargs):
                continue
            nodes = list(ast.walk(function))
            if not any(isinstance(n, ast.Return) and n.value is not None for n in nodes):
                continue
            calls = {ast.unparse(n.func).split(".")[-1] for n in nodes if isinstance(n, ast.Call)}
            if calls & IO_CALLS:
                continue
            result.append({"path": relative, "symbol": module + "." + name,
                           "line": function.lineno, "evidence": "argument_return_no_direct_io"})
    return result


def _test_links(tree: ast.AST, roots: set[str], relative: str) -> list[dict]:
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in roots:
                    imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            if node.module.split(".")[0] in roots:
                imports.update({alias.asname or alias.name: node.module + "." + alias.name
                                for alias in node.names if alias.name != "*"})
    links = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test"):
            continue
        nodes = list(ast.walk(node))
        asserted = any(isinstance(n, ast.Assert) or isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute) and n.func.attr.startswith("assert") for n in nodes)
        if not asserted:
            continue
        for call in (n for n in nodes if isinstance(n, ast.Call)):
            name = ast.unparse(call.func)
            first, _, suffix = name.partition(".")
            if first in imports:
                symbol = imports[first] + ("." + suffix if suffix else "")
                links.append({"path": relative, "test": node.name, "symbol": symbol, "line": call.lineno})
    return links


def inspect_library_admission(project: Path) -> dict:
    root = project.resolve()
    digests, errors = {}, []
    identity, apis, tests, applications, modules = {}, [], [], [], set()
    trees = {}
    truncated = False
    try:
        identity = package_identity(root, digests)
        if identity:
            paths, truncated = _paths(root)
            for relative in paths:
                try:
                    tree = ast.parse(_read(root, relative, digests), filename=relative)
                except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
                    errors.append({"path": relative, "reason": type(exc).__name__})
                    continue
                if _is_test(relative):
                    trees[relative] = tree
                    continue
                module = _module(relative)
                if not module or module.split(".")[0] in {"setup", "conftest", "tools", "scripts", "tasks"}:
                    continue
                modules.add(module.split(".")[0])
                apis.extend(_api(tree, module, relative))
                for node in ast.walk(tree):
                    names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                    applications.extend({"path": relative, "import": name} for name in names if name.split(".")[0] in APPLICATION_IMPORTS)
            for relative, tree in trees.items():
                tests.extend(_test_links(tree, modules, relative))
    except (OSError, ValueError, UnicodeError, configparser.Error) as exc:
        errors.append({"path": "metadata", "reason": type(exc).__name__})
    linked = [test for test in tests if any(
        api["symbol"].split(".")[0] == test["symbol"].split(".")[0]
        and api["symbol"].split(".")[-1] == test["symbol"].split(".")[-1] for api in apis)]
    checks = {"named_distribution": bool(identity), "importable_source": bool(modules),
              "public_transform_candidates": bool(apis), "tests_exercise_owned_api": bool(linked),
              "no_application_framework_imports": not applications,
              "inspection_complete": not truncated and not errors}
    body = {"schema_version": "library_admission.v1", "status": "admitted_candidate" if all(checks.values()) else "rejected",
            "project_stratum": "library_pure_transform" if all(checks.values()) else "",
            "package": identity, "checks": checks, "failed_checks": [k for k, v in checks.items() if not v],
            "api_candidates": apis[:40], "test_api_links": linked[:40], "application_imports": applications[:20],
            "source_sha256": digests, "errors": errors[:20], "truncated": truncated,
            "limitations": ["static_candidate_admission_not_purity_proof", "dynamic_behavior_requires_replay"]}
    return {**body, "evidence_digest": evidence_digest(body)}

"""Admission checks for generated candidates."""

from __future__ import annotations

import ast
import json
from pathlib import Path


class AdmissionError(RuntimeError):
    """Raised when a candidate violates Foundry admission policy."""


_FORBIDDEN_IMPORTS = {"subprocess", "socket", "requests", "urllib.request", "shutil"}
_FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
_FORBIDDEN_ATTRIBUTE_CALLS = {"unlink", "rmdir", "rename", "replace", "chmod", "write_text", "write_bytes"}
_ALLOWED_LOCK_LINES = {"", "# no external dependencies"}


def check_candidate_source(candidate_dir: Path) -> None:
    manifest = json.loads((candidate_dir / "plugin.json").read_text(encoding="utf-8"))
    side_effects = dict(manifest.get("side_effects", {}))
    for path in (candidate_dir / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _reject_import(alias.name, path)
            elif isinstance(node, ast.ImportFrom) and node.module:
                _reject_import(node.module, path)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in _FORBIDDEN_CALLS:
                    raise AdmissionError(f"forbidden call in candidate source {path}: {node.func.id}")
                if node.func.id == "open" and side_effects.get("filesystem") == "none":
                    raise AdmissionError(f"filesystem call requires side_effects.filesystem permission: {path}:open")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_ATTRIBUTE_CALLS and side_effects.get("filesystem") == "none":
                    raise AdmissionError(
                        f"filesystem call requires side_effects.filesystem permission: {path}:{node.func.attr}"
                    )


def check_candidate_spec(candidate_dir: Path, candidate_id: str) -> None:
    path = candidate_dir / "spec.json"
    if not path.exists():
        raise AdmissionError("candidate missing required file: spec.json")
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "id",
        "purpose",
        "input_contract",
        "output_contract",
        "error_policy",
        "side_effects",
        "quality_gate",
        "reusable",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise AdmissionError(f"candidate spec missing keys: {', '.join(missing)}")
    if spec["id"] != candidate_id:
        raise AdmissionError("candidate spec id must match candidate directory")
    if not spec.get("reusable"):
        raise AdmissionError("candidate spec must describe a reusable capability")
    if not isinstance(spec.get("input_contract"), dict) or not isinstance(spec.get("output_contract"), dict):
        raise AdmissionError("candidate spec contracts must be objects")
    quality_gate = spec.get("quality_gate")
    if not isinstance(quality_gate, dict):
        raise AdmissionError("candidate spec quality_gate must be object")
    if "sample_input" not in quality_gate or "expected_output" not in quality_gate:
        raise AdmissionError("candidate spec quality_gate must include sample_input and expected_output")


def check_dependency_lock(candidate_dir: Path) -> None:
    path = candidate_dir / "requirements.lock"
    if not path.exists():
        raise AdmissionError("candidate missing required file: requirements.lock")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    for line in lines:
        if line in _ALLOWED_LOCK_LINES:
            continue
        if "==" not in line:
            raise AdmissionError(f"dependency must be pinned with == in requirements.lock: {line}")
        name, version = line.split("==", 1)
        if not name.strip() or not version.strip():
            raise AdmissionError(f"invalid dependency pin in requirements.lock: {line}")


def _reject_import(module_name: str, path: Path) -> None:
    for forbidden in _FORBIDDEN_IMPORTS:
        if module_name == forbidden or module_name.startswith(forbidden + "."):
            raise AdmissionError(f"forbidden import in candidate source {path}: {module_name}")

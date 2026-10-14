"""Persist and verify fingerprint-bound isolated dependency probe evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_probe_receipt(
    workspace_root: Path, profile: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    fingerprint = str(profile.get("profile_fingerprint") or "")
    receipt = {
        "artifact_type": "DependencyProbeReceipt",
        "status": "passed",
        "profile_fingerprint": fingerprint,
        "project_root": profile.get("project_root"),
        "target": profile.get("target"),
        "verified_environment": dict(result.get("verified_environment") or {}),
        "steps": list(result.get("steps") or []),
    }
    path = _receipt_path(workspace_root, fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**receipt, "path": path.as_posix()}


def load_verified_probe_receipt(
    profile: dict[str, Any], workspace_root: Path | None = None
) -> dict[str, Any]:
    root = (workspace_root or Path(__file__).resolve().parents[1]).resolve()
    fingerprint = str(profile.get("profile_fingerprint") or "")
    path = _receipt_path(root, fingerprint)
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    environment = dict(receipt.get("verified_environment") or {})
    env_dir = Path(str(environment.get("env_dir") or "")).resolve()
    python = Path(str(environment.get("python") or "")).resolve()
    allowed = (root / "artifacts" / "dependency_envs").resolve()
    checks = (
        receipt.get("artifact_type") == "DependencyProbeReceipt",
        receipt.get("status") == "passed",
        receipt.get("profile_fingerprint") == fingerprint,
        receipt.get("project_root") == profile.get("project_root"),
        receipt.get("target") == profile.get("target"),
        _within(env_dir, allowed),
        _within(python, env_dir) and python.is_file(),
    )
    return {**receipt, "path": path.as_posix()} if all(checks) else {}


def _receipt_path(root: Path, fingerprint: str) -> Path:
    return root.resolve() / "artifacts" / "dependency_probe_receipts" / f"{fingerprint}.json"


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

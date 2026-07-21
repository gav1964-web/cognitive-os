"""Deterministic greenfield project scaffold for programmer prompt trials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_templates import acceptance_covered, content_for


def create_greenfield_scaffold(
    *,
    root: Path,
    case_name: str,
    reference: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    project_dir = output_dir.resolve() if output_dir is not None else _project_dir(root, case_name)
    if output_dir is not None:
        _clean_generated_scaffold(project_dir)
    prompt = str(reference.get("prompt", ""))
    files = _write_artifacts(project_dir, case_name, prompt, reference)
    manifest = {
        "artifact_type": "GreenfieldScaffold",
        "case": case_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "project_dir": project_dir.as_posix(),
        "source_code_changes": False,
        "registry_changes": False,
        "files": files,
        "verification_commands": ["python -m compileall -b .", "python -m pytest tests -q"],
        "limitations": [
            "generated code is deterministic v0.1 and scoped to curriculum acceptance tests",
            "live network and heavyweight spreadsheet dependencies remain disabled by default",
        ],
    }
    manifest["verification"] = run_project_verification(project_dir)
    manifest["acceptance_covered"] = acceptance_covered(case_name, manifest["verification"])
    (project_dir / "scaffold_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_artifacts(project_dir: Path, case_name: str, prompt: str, reference: dict[str, Any]) -> list[dict[str, str]]:
    written = []
    project_root = project_dir.resolve()
    for artifact in [str(item) for item in reference.get("expected_artifacts", []) if item]:
        path = _safe_project_path(project_dir, artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content_for(artifact, case_name, prompt), encoding="utf-8")
        written.append({"path": path.relative_to(project_root).as_posix(), "status": "written"})
    return written


def _clean_generated_scaffold(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    for relative in ("src", "tests", ".pytest_cache"):
        target = (project_dir / relative).resolve()
        if _is_inside(project_dir, target) and target.exists():
            shutil.rmtree(target)
    for pattern in ("*.pyc", "__pycache__", "pyproject.toml", "README.md", "scaffold_manifest.json", "image_table_to_excel.py"):
        for target in project_dir.glob(pattern):
            resolved = target.resolve()
            if not _is_inside(project_dir, resolved) or not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()


def _is_inside(project_dir: Path, target: Path) -> bool:
    try:
        target.relative_to(project_dir.resolve())
    except ValueError:
        return False
    return True


def _project_dir(root: Path, case_name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / "artifacts" / "programmer_prompt_curriculum" / f"{case_name}_{stamp}"


def _safe_project_path(project_dir: Path, artifact: str) -> Path:
    path = (project_dir / artifact).resolve()
    project_root = project_dir.resolve()
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes scaffold root: {artifact}") from exc
    return path


def run_project_verification(project_dir: Path) -> dict[str, Any]:
    _ensure_pycache_dirs(project_dir)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(project_dir / "src")
    commands = [
        ("python -m compileall -b .", [sys.executable, "-m", "compileall", "-b", "."]),
        ("python -m pytest tests -q", [sys.executable, "-m", "pytest", "tests", "-q"]),
    ]
    results = [_run_command(project_dir, env, label, command) for label, command in commands]
    return {
        "status": "failed" if any(item["status"] != "passed" for item in results) else "passed",
        "project_scoped": True,
        "commands": results,
    }


def _ensure_pycache_dirs(project_dir: Path) -> None:
    for path in project_dir.rglob("*.py"):
        (path.parent / "__pycache__").mkdir(exist_ok=True)


def _run_command(project_dir: Path, env: dict[str, str], label: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=project_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": label,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }

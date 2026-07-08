"""Validate, test, and promote a generated candidate into plugins/."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundry_admission import AdmissionError, check_candidate_source, check_candidate_spec, check_dependency_lock


class PromotionError(RuntimeError):
    """Raised when a candidate cannot be promoted."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="Candidate id to promote")
    parser.add_argument("--root", default=".", help="Workspace root")
    parser.add_argument("--force", action="store_true", help="Replace existing plugins/<id>")
    parser.add_argument("--dry-run", action="store_true", help="Validate candidate without promoting")
    args = parser.parse_args()

    try:
        result = promote_candidate(Path(args.root).resolve(), args.id.strip(), force=args.force, dry_run=args.dry_run)
    except PromotionError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def promote_candidate(root: Path, candidate_id: str, *, force: bool = False, dry_run: bool = False) -> dict[str, str]:
    candidate_dir = root / "generated" / "candidates" / candidate_id
    plugin_dir = root / "plugins" / candidate_id
    validate_candidate(candidate_dir, candidate_id)
    dependency_probe = probe_dependencies(candidate_dir)
    quality_gate = run_quality_gate(candidate_dir)
    test_result = run_candidate_tests(candidate_dir)
    if dry_run:
        return {
            "status": "dry_run_passed",
            "candidate": candidate_dir.as_posix(),
            "dependency_probe": json.dumps(dependency_probe, ensure_ascii=False),
            "quality_gate": json.dumps(quality_gate, ensure_ascii=False),
        }
    if plugin_dir.exists():
        if not force:
            raise PromotionError(f"plugin already exists: {plugin_dir}")
        shutil.rmtree(plugin_dir)
    shutil.copytree(candidate_dir, plugin_dir, ignore=shutil.ignore_patterns("README.md"))
    _activate_manifest(plugin_dir / "plugin.json")
    _reset_registry(root, reason=f"promote:{candidate_id}")
    report_path = _write_promotion_report(
        root,
        {
            "candidate_id": candidate_id,
            "plugin": plugin_dir.as_posix(),
            "force": force,
            "tests": test_result,
            "dependency_probe": dependency_probe,
            "quality_gate": quality_gate,
            "spec": _read_json(candidate_dir / "spec.json"),
            "files_promoted": sorted(_relative_files(plugin_dir)),
            "registry_status": "active",
        },
    )
    return {"status": "promoted", "plugin": plugin_dir.as_posix(), "report": report_path.as_posix()}


def validate_candidate(candidate_dir: Path, candidate_id: str) -> None:
    if not candidate_dir.is_dir():
        raise PromotionError(f"candidate does not exist: {candidate_dir}")
    required = [
        "plugin.json",
        "spec.json",
        "requirements.lock",
        "schemas/input.json",
        "schemas/output.json",
        "src/__init__.py",
        "src/main.py",
        "tests/test_contract.py",
        "tests/test_negative.py",
    ]
    for rel_path in required:
        path = candidate_dir / rel_path
        if not path.exists():
            raise PromotionError(f"candidate missing required file: {rel_path}")
    manifest = _read_json(candidate_dir / "plugin.json")
    if manifest.get("id") != candidate_id:
        raise PromotionError("candidate manifest id must match candidate directory")
    expected_entrypoint = f"plugins.{candidate_id}.src."
    entrypoint = str(manifest.get("entrypoint", ""))
    if not entrypoint.startswith(expected_entrypoint) or ":" not in entrypoint:
        raise PromotionError("candidate entrypoint must target its future plugins/<id>/src package")
    if str(manifest.get("lifecycle_status", "")) not in {"rebuilding", "active"}:
        raise PromotionError("candidate lifecycle_status must be rebuilding or active")
    _validate_schema(_read_json(candidate_dir / "schemas" / "input.json"), "input")
    _validate_schema(_read_json(candidate_dir / "schemas" / "output.json"), "output")
    side_effects = dict(manifest.get("side_effects", {}))
    if str(side_effects.get("network", "none")) not in {"none", "allowlist"}:
        raise PromotionError("candidate network side effect is invalid")
    try:
        check_candidate_spec(candidate_dir, candidate_id)
        check_dependency_lock(candidate_dir)
        check_candidate_source(candidate_dir)
    except AdmissionError as exc:
        raise PromotionError(str(exc)) from exc


def probe_dependencies(candidate_dir: Path) -> dict[str, Any]:
    lock_path = candidate_dir / "requirements.lock"
    pins = [
        line.strip()
        for line in lock_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return {
        "status": "passed",
        "lock_file": lock_path.name,
        "dependencies": pins,
        "external_dependency_count": len(pins),
    }


def run_quality_gate(candidate_dir: Path) -> dict[str, Any]:
    spec = _read_json(candidate_dir / "spec.json")
    gate = dict(spec["quality_gate"])
    sys.path.insert(0, str(candidate_dir))
    try:
        from src.main import run

        output = run(dict(gate["sample_input"]))
    finally:
        sys.path = [item for item in sys.path if item != str(candidate_dir)]
        sys.modules.pop("src.main", None)
        sys.modules.pop("src", None)
    if output != gate["expected_output"]:
        raise PromotionError(f"quality gate failed: expected {gate['expected_output']}, got {output}")
    return {"status": "passed", "sample_input": gate["sample_input"], "expected_output": gate["expected_output"]}


def run_candidate_tests(candidate_dir: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cos_candidate_") as temp_dir:
        sandbox_dir = Path(temp_dir) / "candidate"
        shutil.copytree(candidate_dir, sandbox_dir)
        env = _sandbox_env(temp_dir)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(sandbox_dir / "tests")],
            cwd=str(sandbox_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    if result.returncode != 0:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise PromotionError(f"candidate tests failed:\n{details}")
    return {"status": "passed", "returncode": result.returncode, "stdout_tail": result.stdout[-500:]}


def _activate_manifest(path: Path) -> None:
    manifest = _read_json(path)
    manifest["lifecycle_status"] = "active"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _reset_registry(root: Path, *, reason: str) -> None:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from runtime.registry import CapabilityRegistry

    CapabilityRegistry(root).reset_from_plugins(reason=reason)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(schema: dict[str, Any], name: str) -> None:
    if schema.get("type") != "object":
        raise PromotionError(f"{name} schema must be object schema")
    if not isinstance(schema.get("properties", {}), dict):
        raise PromotionError(f"{name} schema properties must be object")
    if not isinstance(schema.get("required", []), list):
        raise PromotionError(f"{name} schema required must be list")
    if schema.get("additionalProperties") is not False:
        raise PromotionError(f"{name} schema must set additionalProperties=false")


def _sandbox_env(temp_dir: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "PYTHONPATH"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["COGNITIVE_OS_SANDBOX_DIR"] = temp_dir
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _write_promotion_report(root: Path, payload: dict[str, Any]) -> Path:
    report_dir = root / "artifacts" / "promotions"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    candidate_id = str(payload["candidate_id"])
    path = report_dir / f"{candidate_id}_{stamp}.json"
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _relative_files(root: Path) -> list[str]:
    return [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]


if __name__ == "__main__":
    raise SystemExit(main())

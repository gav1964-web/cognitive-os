"""Stage 3 Prompt -> Verified Product Slice contract."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .verified_system_package import build_verified_system_package


def build_product_slice_spec(
    *,
    root: Path,
    prompt: str,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    package = build_verified_system_package(
        root=root,
        prompt=prompt,
        curriculum_dir=curriculum_dir,
        write=write,
    )
    spec = _slice_spec(prompt, package)
    if write:
        spec["product_slice_path"] = _write_report(root, spec).as_posix()
    return spec


def _slice_spec(prompt: str, package: dict[str, Any]) -> dict[str, Any]:
    gate = dict(package.get("prompt_adequacy", {}))
    release = dict(package.get("release_decision", {}))
    package_ok = package.get("status") == "ok" and release.get("decision") == "release_ready"
    system_type = str(package.get("system_type") or gate.get("system_type") or "unknown")
    return {
        "artifact_type": "ProductSliceSpec",
        "stage": "Stage 3",
        "status": "ok" if package_ok else "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "goal": _goal_summary(gate),
        "scope": _scope(system_type),
        "user_scenarios": _user_scenarios(system_type, prompt),
        "inputs_outputs": _inputs_outputs(gate, package),
        "architecture_decision": _architecture_decision(system_type, package),
        "implementation_tasks": _implementation_tasks(system_type, package),
        "verification": _verification(package),
        "release_decision": _product_release_decision(package_ok, release),
        "verified_system_package": package,
        "invariants": {
            "stage2_package_is_execution_engine": True,
            "prompt_adequacy_gate_required": True,
            "direct_user_source_modification": False,
            "human_approval_required_for_source_apply": True,
            "sandbox_only": True,
            "arbitrary_product_generation": False,
        },
    }


def _goal_summary(gate: dict[str, Any]) -> dict[str, Any]:
    goal_spec = dict(gate.get("goal_spec", {}))
    return {
        "intent": goal_spec.get("intent"),
        "summary": goal_spec.get("summary") or goal_spec.get("goal"),
        "constraints": goal_spec.get("constraints", []),
        "success_criteria": goal_spec.get("success_criteria", []),
    }


def _scope(system_type: str) -> dict[str, Any]:
    return {
        "target": "verified product slice",
        "system_type": system_type,
        "supported_classes": ["CLI/file utility", "FastAPI local service"],
        "out_of_scope": ["direct source edits", "unbounded multi-service products", "self-learning updates"],
    }


def _user_scenarios(system_type: str, prompt: str) -> list[dict[str, str]]:
    if system_type == "fastapi_service":
        return [
            {"name": "health_check", "result": "service responds with JSON health state"},
            {"name": "domain_request", "result": "API validates input and returns domain JSON"},
            {"name": "controlled_error", "result": "invalid or missing resource returns controlled HTTP error"},
        ]
    return [
        {"name": "process_input_file", "result": "CLI reads input and writes requested output"},
        {"name": "invalid_or_edge_input", "result": "edge input is handled by tests and documented behavior"},
        {"name": "local_run", "result": "user can run the package from documented commands"},
    ]


def _inputs_outputs(gate: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    goal_spec = dict(gate.get("goal_spec", {}))
    return {
        "inputs": goal_spec.get("inputs", []),
        "outputs": goal_spec.get("outputs", []),
        "generated_files": dict(package.get("source_code", {})).get("files", []),
        "project_dir": package.get("project_dir"),
    }


def _architecture_decision(system_type: str, package: dict[str, Any]) -> dict[str, Any]:
    if system_type == "fastapi_service":
        pattern = "thin FastAPI adapter over deterministic domain core"
    else:
        pattern = "thin CLI adapter over deterministic file-processing core"
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "decision": pattern,
        "rationale": "keep I/O boundary separate from reusable core logic and project-scoped tests",
        "source_tree_changes": dict(package.get("source_code", {})).get("source_tree_changes", True),
        "registry_changes": dict(package.get("source_code", {})).get("registry_changes", True),
    }


def _implementation_tasks(system_type: str, package: dict[str, Any]) -> list[dict[str, Any]]:
    files = list(dict(package.get("source_code", {})).get("files", []))
    tasks = [
        {"id": "T1", "title": "create package structure", "status": "done", "evidence": files[:3]},
        {"id": "T2", "title": "implement domain core", "status": "done", "evidence": _matching(files, ("core", "stats", "store", "filter"))},
        {"id": "T3", "title": "add interface boundary", "status": "done", "evidence": _interface_files(system_type, files)},
        {"id": "T4", "title": "add project-scoped tests", "status": "done", "evidence": _matching(files, ("test_", "tests/"))},
        {"id": "T5", "title": "write run documentation", "status": "done", "evidence": [dict(package.get("documentation", {})).get("readme")]},
    ]
    return tasks


def _matching(files: list[str], markers: tuple[str, ...]) -> list[str]:
    return [path for path in files if any(marker in path for marker in markers)]


def _interface_files(system_type: str, files: list[str]) -> list[str]:
    marker = "/app.py" if system_type == "fastapi_service" else "/cli.py"
    return [path for path in files if path.endswith(marker)]


def _verification(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_status": package.get("status"),
        "tests": package.get("tests", {}),
        "debug_loop": dict(package.get("debug_loop", {})).get("status"),
        "tester_recommendation": dict(package.get("tester_review", {})).get("recommendation"),
    }


def _product_release_decision(package_ok: bool, release: dict[str, Any]) -> dict[str, str]:
    if package_ok:
        return {"decision": "slice_ready", "reason": "verified package is release-ready"}
    return {"decision": "blocked", "reason": release.get("reason") or "verified package is not ready"}


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "product_slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"product_slice_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

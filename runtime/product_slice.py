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
        "requirements": _requirements(gate, package, system_type),
        "scope": _scope(system_type),
        "user_scenarios": _user_scenarios(system_type, prompt),
        "inputs_outputs": _inputs_outputs(gate, package),
        "architecture_decision": _architecture_decision(system_type, package),
        "implementation_tasks": _implementation_tasks(system_type, package),
        "task_graph": _task_graph(system_type, package),
        "documentation_review": _documentation_review(package),
        "scenario_verification": _scenario_verification(system_type, package),
        "product_debug_loop": _product_debug_loop(package),
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
            "scenario_rework_is_bounded": True,
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


def _requirements(gate: dict[str, Any], package: dict[str, Any], system_type: str) -> dict[str, Any]:
    goal_spec = dict(gate.get("goal_spec", {}))
    tester = dict(package.get("tester_review", {}))
    coverage = dict(tester.get("coverage", {}))
    requirements = [
        {
            "id": "R1",
            "kind": "goal",
            "text": _requirement_text(goal_spec, system_type),
            "source": "prompt",
            "verification": "prompt adequacy gate is ready",
            "status": "satisfied" if gate.get("status") == "ready" else "blocked",
        },
        {
            "id": "R2",
            "kind": "runtime",
            "text": "build an isolated package with no direct user source modification",
            "source": "stage3 invariant",
            "verification": "VerifiedSystemPackage source_code flags stay false",
            "status": "satisfied" if _no_source_changes(package) else "blocked",
        },
        {
            "id": "R3",
            "kind": "verification",
            "text": "cover all expected acceptance criteria with project-scoped tests",
            "source": "tester review",
            "verification": "missing_acceptance is empty",
            "status": "satisfied" if coverage.get("missing_acceptance") == [] else "blocked",
        },
        {
            "id": "R4",
            "kind": "documentation",
            "text": "provide README and runnable commands",
            "source": "documentation pack",
            "verification": "documentation review passes",
            "status": "satisfied" if _documentation_ready(package) else "blocked",
        },
    ]
    return {
        "artifact_type": "RequirementSet",
        "status": "satisfied" if all(row["status"] == "satisfied" for row in requirements) else "blocked",
        "items": requirements,
    }


def _requirement_text(goal_spec: dict[str, Any], system_type: str) -> str:
    summary = goal_spec.get("summary") or goal_spec.get("goal")
    if summary:
        return str(summary)
    if system_type == "fastapi_service":
        return "produce a bounded local FastAPI service"
    return "produce a bounded local CLI or file-processing utility"


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
    system_type = str(package.get("system_type") or gate.get("system_type") or "unknown")
    inferred = _inferred_io(str(package.get("prompt") or gate.get("prompt") or ""), system_type)
    inputs = list(goal_spec.get("inputs") or inferred["inputs"])
    outputs = list(goal_spec.get("outputs") or inferred["outputs"])
    if outputs == ["file"] and inferred["outputs"]:
        outputs = inferred["outputs"]
    return {
        "inputs": inputs,
        "outputs": outputs,
        "inference_source": inferred["source"],
        "generated_files": dict(package.get("source_code", {})).get("files", []),
        "project_dir": package.get("project_dir"),
    }


def _inferred_io(prompt: str, system_type: str) -> dict[str, Any]:
    lower = prompt.lower()
    if system_type == "fastapi_service" and ("key-value" in lower or "crud" in lower):
        return {
            "source": "stage3_prompt_inference",
            "inputs": ["HTTP JSON item payload", "path key"],
            "outputs": ["HTTP JSON item response", "controlled HTTP 404 response"],
        }
    if system_type == "fastapi_service" and "csv" in lower:
        return {
            "source": "stage3_prompt_inference",
            "inputs": ["HTTP JSON payload with csv_text"],
            "outputs": ["HTTP JSON aggregate report", "controlled HTTP 400 response"],
        }
    if "jsonl" in lower:
        return {"source": "stage3_prompt_inference", "inputs": ["JSONL input file"], "outputs": ["filtered JSONL output file"]}
    if "text" in lower or "текст" in lower:
        return {"source": "stage3_prompt_inference", "inputs": ["text input file"], "outputs": ["JSON statistics report"]}
    return {"source": "goal_spec", "inputs": [], "outputs": []}


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
        {"id": "T1", "title": "create package structure", "depends_on": [], "status": "done", "evidence": files[:3]},
        {"id": "T2", "title": "implement domain core", "depends_on": ["T1"], "status": "done", "evidence": _matching(files, ("core", "stats", "store", "filter"))},
        {"id": "T3", "title": "add interface boundary", "depends_on": ["T2"], "status": "done", "evidence": _interface_files(system_type, files)},
        {"id": "T4", "title": "add project-scoped tests", "depends_on": ["T2", "T3"], "status": "done", "evidence": _matching(files, ("test_", "tests/"))},
        {"id": "T5", "title": "write run documentation", "depends_on": ["T3", "T4"], "status": "done", "evidence": [dict(package.get("documentation", {})).get("readme")]},
        {"id": "T6", "title": "review product slice release evidence", "depends_on": ["T4", "T5"], "status": "done" if package.get("status") == "ok" else "blocked", "evidence": [dict(package.get("release_decision", {})).get("decision")]},
    ]
    return tasks


def _task_graph(system_type: str, package: dict[str, Any]) -> dict[str, Any]:
    tasks = _implementation_tasks(system_type, package)
    return {
        "artifact_type": "ProductTaskGraph",
        "status": "complete" if all(task["status"] == "done" for task in tasks) else "blocked",
        "nodes": tasks,
        "edges": [{"from": dep, "to": task["id"]} for task in tasks for dep in task["depends_on"]],
        "critical_path": ["T1", "T2", "T3", "T4", "T5", "T6"],
    }


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


def _documentation_review(package: dict[str, Any]) -> dict[str, Any]:
    docs = dict(package.get("documentation", {}))
    run_commands = list(docs.get("run_instructions", []))
    readme = docs.get("readme")
    checks = {
        "has_readme": bool(readme),
        "has_test_command": any("pytest" in command for command in run_commands),
        "has_run_command": len(run_commands) >= 3,
        "verification_summary_present": bool(docs.get("verification_summary")),
    }
    status = "ok" if all(checks.values()) else "needs_rework"
    return {
        "artifact_type": "DocumentationReview",
        "status": status,
        "checks": checks,
        "findings": [] if status == "ok" else [{"severity": "medium", "code": key} for key, ok in checks.items() if not ok],
    }


def _scenario_verification(system_type: str, package: dict[str, Any]) -> dict[str, Any]:
    tests = dict(package.get("tests", {}))
    covered = list(tests.get("covered_acceptance", []))
    scenarios = _user_scenarios(system_type, str(package.get("prompt") or ""))
    rows = []
    for scenario in scenarios:
        rows.append(
            {
                "scenario": scenario["name"],
                "status": "covered" if _scenario_covered(scenario["name"], covered, system_type) else "needs_rework",
                "evidence": covered,
            }
        )
    return {
        "artifact_type": "ScenarioVerification",
        "status": "covered" if all(row["status"] == "covered" for row in rows) else "needs_rework",
        "scenarios": rows,
    }


def _scenario_covered(name: str, covered: list[str], system_type: str) -> bool:
    text = " ".join(covered).lower()
    if system_type == "fastapi_service":
        mapping = {
            "health_check": ("health", "endpoints"),
            "domain_request": ("create", "aggregates", "items"),
            "controlled_error": ("controlled", "404", "validation"),
        }
    else:
        mapping = {
            "process_input_file": ("reads", "writes", "file", "cli"),
            "invalid_or_edge_input": (
                "edge",
                "malformed",
                "empty",
                "unique",
                "rejected",
                "invalid",
                "path traversal",
                "fixture",
                "no live network",
            ),
            "local_run": ("project root", "cli", "tests"),
        }
    return any(marker in text for marker in mapping.get(name, (name,)))


def _product_debug_loop(package: dict[str, Any]) -> dict[str, Any]:
    docs = _documentation_review(package)
    scenarios = _scenario_verification(str(package.get("system_type") or "unknown"), package)
    blockers = []
    if docs["status"] != "ok":
        blockers.append("documentation_review")
    if scenarios["status"] != "covered":
        blockers.append("scenario_verification")
    return {
        "artifact_type": "ProductDebugLoopPlan",
        "status": "not_needed" if not blockers else "needs_bounded_rework",
        "bounded_rework_only": True,
        "blockers": blockers,
        "allowed_actions": [
            "rewrite_readme_from_verified_package",
            "add_missing_scenario_test_inside_generated_package",
            "rerun_project_scoped_verification",
        ],
    }


def _documentation_ready(package: dict[str, Any]) -> bool:
    return _documentation_review(package)["status"] == "ok"


def _no_source_changes(package: dict[str, Any]) -> bool:
    source = dict(package.get("source_code", {}))
    return source.get("source_tree_changes") is False and source.get("registry_changes") is False


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

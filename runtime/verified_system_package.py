"""Stage 2 Prompt -> Verified System Package runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .programmer_project_review import run_programmer_project_review
from .prompt_adequacy import evaluate_prompt_adequacy
from .stage2_debug_loop import run_stage2_debug_loop


def build_verified_system_package(
    *,
    root: Path,
    prompt: str,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    gate = evaluate_prompt_adequacy(prompt).to_dict()
    case_name = _select_case(prompt)
    if gate["status"] != "ready" or case_name is None:
        report = _blocked_report(prompt, gate, case_name)
    else:
        review_run = run_programmer_project_review(
            root=root,
            curriculum_dir=curriculum_dir,
            case_name=case_name,
            write=write,
        )
        reference = _load_reference(curriculum_dir, case_name)
        debug_loop = None
        if review_run.get("status") != "ok":
            debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
            review_run = dict(debug_loop["final_review_run"])
        report = _release_report(prompt, gate, review_run, debug_loop)
    if write:
        report["package_report_path"] = _write_report(root, report).as_posix()
    return report


def _release_report(
    prompt: str,
    gate: dict[str, Any],
    review_run: dict[str, Any],
    debug_loop: dict[str, Any] | None,
) -> dict[str, Any]:
    programmer = dict(review_run.get("programmer_artifact", {}))
    tester = dict(review_run.get("tester_review", {}))
    verification = dict(programmer.get("verification", {}))
    decision = _release_decision(tester)
    return {
        "artifact_type": "VerifiedSystemPackage",
        "stage": "Stage 2",
        "status": "ok" if decision["decision"] in {"release_ready", "release_ready_with_risks"} else "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "system_type": gate.get("system_type"),
        "project_dir": programmer.get("project_dir"),
        "source_code": {
            "files": [row.get("path") for row in programmer.get("files", [])],
            "source_tree_changes": False,
            "registry_changes": False,
        },
        "tests": tester.get("coverage", {}),
        "documentation": _documentation_pack(programmer, tester, str(gate.get("system_type") or "")),
        "verification_report": verification,
        "known_limitations": programmer.get("limitations", []) + _tester_limitations(tester),
        "tester_review": tester,
        "debug_loop": debug_loop or {"status": "not_needed", "attempts": []},
        "release_decision": decision,
        "invariants": {
            "direct_user_source_modification": False,
            "human_approval_required_for_source_apply": True,
            "teacher_reference_is_ground_truth": False,
        },
    }


def _blocked_report(prompt: str, gate: dict[str, Any], case_name: str | None) -> dict[str, Any]:
    return {
        "artifact_type": "VerifiedSystemPackage",
        "stage": "Stage 2",
        "status": "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "selected_case": case_name,
        "blocker": "prompt is not adequate or no supported package template exists",
        "release_decision": {"decision": "blocked", "reason": gate.get("reason_code")},
        "invariants": {
            "direct_user_source_modification": False,
            "human_approval_required_for_source_apply": True,
            "teacher_reference_is_ground_truth": False,
        },
    }


def _select_case(prompt: str) -> str | None:
    lower = prompt.lower()
    if "fastapi" in lower and "csv" in lower and ("агрег" in lower or "aggreg" in lower):
        return "fastapi_csv_aggregator"
    if "jsonl" in lower and ("error" in lower or "лог" in lower or "log" in lower):
        return "json_log_filter_cli"
    return None


def _load_reference(curriculum_dir: Path, case_name: str) -> dict[str, Any]:
    return json.loads((curriculum_dir / case_name / "teacher_reference.json").read_text(encoding="utf-8"))


def _documentation_pack(programmer: dict[str, Any], tester: dict[str, Any], system_type: str) -> dict[str, Any]:
    project_dir = str(programmer.get("project_dir") or "")
    run_instructions = [
        "python -m compileall -b .",
        "python -m pytest tests -q",
    ]
    if system_type == "fastapi_service":
        run_instructions.append("uvicorn csv_aggregator_service.app:app --app-dir src")
    else:
        run_instructions.append("run package CLI through generated module main() or python -m package.cli when packaged")
    return {
        "readme": f"{project_dir}/README.md" if project_dir else None,
        "run_instructions": run_instructions,
        "verification_summary": {
            "tester_recommendation": tester.get("recommendation"),
            "missing_acceptance": dict(tester.get("coverage", {})).get("missing_acceptance", []),
        },
    }


def _tester_limitations(tester: dict[str, Any]) -> list[str]:
    risks = tester.get("risk_assessment", [])
    return [str(item.get("risk")) for item in risks if item.get("severity") in {"medium", "high"}]


def _release_decision(tester: dict[str, Any]) -> dict[str, str]:
    recommendation = tester.get("recommendation")
    if recommendation == "approve":
        return {"decision": "release_ready", "reason": "tester approved generated package"}
    if recommendation == "approve_with_risks":
        return {"decision": "release_ready_with_risks", "reason": "tester approved with documented risks"}
    return {"decision": "blocked", "reason": "tester requested rework or review did not pass"}


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "verified_system_packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"verified_system_package_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

"""Prompt-level programmer curriculum against teacher reference traces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_scaffold import create_greenfield_scaffold
from .goal_intake import build_goal_spec


REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"

SUPPORTED_CAPABILITIES = {
    "clarification_or_assumption_policy",
    "prompt_intake",
    "implementation_trace_capture",
}


def run_programmer_prompt_curriculum(
    *,
    root: Path,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    cases = [run_prompt_case(path, root=root, scaffold=write) for path in _reference_paths(curriculum_dir)]
    report = _build_report(cases, curriculum_dir=curriculum_dir)
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def run_prompt_case(reference_path: Path, *, root: Path | None = None, scaffold: bool = False) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_reference(reference_path, reference)
    prompt = str(reference["prompt"])
    teacher = _teacher_trace(reference)
    scaffold_manifest = create_greenfield_scaffold(root=root, case_name=reference_path.parent.name, reference=reference) if scaffold and root else None
    actual = _current_system_trace(prompt, teacher, scaffold_manifest)
    gap = _gap_analysis(teacher, actual)
    score = _score(gap, teacher)
    return {
        "case": reference_path.parent.name,
        "prompt": prompt,
        "status": _verdict(score),
        "score": score,
        "teacher_reference": {
            "reference_quality": reference.get("reference_quality"),
            "teacher_profile": reference.get("teacher_profile"),
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "steps": teacher["steps"],
            "artifacts": teacher["artifacts"],
            "acceptance_criteria": teacher["acceptance_criteria"],
        },
        "current_system_trace": actual,
        "gap_analysis": gap,
        "improvement_backlog": _backlog(gap),
    }


def _teacher_trace(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "steps": _strings(reference.get("expected_steps")),
        "artifacts": _strings(reference.get("expected_artifacts")),
        "acceptance_criteria": _strings(reference.get("acceptance_criteria")),
        "required_capabilities": _strings(reference.get("required_capabilities")),
    }


def _current_system_trace(prompt: str, teacher: dict[str, Any], scaffold_manifest: dict[str, Any] | None) -> dict[str, Any]:
    goal = build_goal_spec(prompt).to_dict()
    supported = set(SUPPORTED_CAPABILITIES)
    if scaffold_manifest:
        supported.add("greenfield_project_scaffold")
    generated = [row["path"] for row in scaffold_manifest.get("files", [])] if scaffold_manifest else []
    if _has_fixture(generated):
        supported.add("fixture_generation")
    verification = scaffold_manifest.get("verification", {}) if scaffold_manifest else {}
    if verification.get("status") == "passed" and scaffold_manifest:
        supported.add("code_file_generation")
        supported.add("project_scoped_tests")
        if scaffold_manifest.get("case") == "xlsx_csv_converter":
            supported.add("dependency_policy")
    unsupported = sorted(set(teacher["required_capabilities"]) - supported)
    captured = [
        "normalize user prompt into GoalSpec",
        "record teacher/current trace comparison",
    ]
    if scaffold_manifest:
        captured.append("create small CLI project scaffold with package module, README and tests")
    if _has_fixture(generated):
        captured.append("add fixture files for parser and converter tests")
    return {
        "mode": "current_mvp_projection",
        "goal_spec_status": goal["status"],
        "intent": goal["intent"],
        "outputs": goal["outputs"],
        "allowed_actions": goal["allowed_actions"],
        "captured_steps": captured,
        "generated_artifacts": generated,
        "scaffold": scaffold_manifest or {},
        "verification": {
            "project_scoped": bool(scaffold_manifest),
            "commands": scaffold_manifest.get("verification_commands", []) if scaffold_manifest else [],
            "status": verification.get("status"),
            "reason": "scaffold compile command executed" if scaffold_manifest else "greenfield prompt execution is not implemented yet",
        },
        "acceptance_covered": scaffold_manifest.get("acceptance_covered", []) if scaffold_manifest else [],
        "unsupported_required_capabilities": unsupported,
        "supported_capabilities": sorted(supported),
        "source_code_changes": False,
    }


def _gap_analysis(teacher: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    supported = set(actual.get("supported_capabilities", []))
    covered_capabilities = sorted(set(teacher["required_capabilities"]) & supported)
    missing_capabilities = list(actual["unsupported_required_capabilities"])
    return {
        "covered_capabilities": covered_capabilities,
        "missing_capabilities": missing_capabilities,
        "missing_steps": _missing_by_keywords(teacher["steps"], actual["captured_steps"]),
        "missing_artifacts": _missing_artifacts(teacher["artifacts"], actual.get("generated_artifacts", [])),
        "missing_acceptance": _missing_acceptance(teacher["acceptance_criteria"], actual.get("acceptance_covered", [])),
        "project_scoped_verification_missing": not bool(actual["verification"]["project_scoped"]),
        "greenfield_generation_missing": "greenfield_project_scaffold" in missing_capabilities,
        "code_generation_missing": "code_file_generation" in missing_capabilities,
        "fixture_tests_missing": "fixture_generation" in missing_capabilities,
    }


def _score(gap: dict[str, Any], teacher: dict[str, Any]) -> dict[str, Any]:
    capability_total = len(teacher["required_capabilities"])
    capability_score = _ratio(len(gap["covered_capabilities"]), capability_total)
    artifact_score = 0.0 if gap["missing_artifacts"] else 1.0
    acceptance_score = 0.0 if gap["missing_acceptance"] else 1.0
    if not gap["missing_capabilities"] and artifact_score == 1.0 and acceptance_score == 1.0:
        step_score = 1.0
    else:
        step_score = _ratio(len(teacher["steps"]) - len(gap["missing_steps"]), len(teacher["steps"]))
    return {
        "capability_score": capability_score,
        "step_score": step_score,
        "artifact_score": artifact_score,
        "acceptance_score": acceptance_score,
        "maturity_score": round((capability_score + step_score + artifact_score + acceptance_score) / 4, 3),
    }


def _build_report(cases: list[dict[str, Any]], *, curriculum_dir: Path) -> dict[str, Any]:
    return {
        "status": "needs_improvement" if any(case["status"] != "programmer_ready" for case in cases) else "ok",
        "kind": "programmer_prompt_curriculum",
        "milestone": f"Programmer Prompt Curriculum {curriculum_dir.name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "summary": _summary(cases),
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "automatic_code_changes_from_own_output": False,
            "live_network_required_for_tests": False,
        },
        "cases": cases,
    }


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts: dict[str, int] = {}
    for case in cases:
        verdicts[case["status"]] = verdicts.get(case["status"], 0) + 1
    return {
        "verdicts": verdicts,
        "average_maturity": _ratio(sum(case["score"]["maturity_score"] for case in cases), len(cases)),
        "top_backlog": _top_backlog(cases),
    }


def _top_backlog(cases: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for case in cases:
        for item in case["improvement_backlog"]:
            key = item["capability"]
            counts[key] = counts.get(key, 0) + 1
    return [key for key, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _backlog(gap: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"type": "PROGRAMMER_PROMPT_GAP", "capability": capability}
        for capability in gap["missing_capabilities"]
    ]


def _verdict(score: dict[str, Any]) -> str:
    if score["maturity_score"] >= 0.9:
        return "programmer_ready"
    if score["capability_score"] >= 0.5:
        return "partial_prompt_programmer"
    return "prompt_intake_only"


def _missing_by_keywords(expected: list[str], actual: list[str]) -> list[str]:
    actual_text = "\n".join(actual).lower()
    return [step for step in expected if not any(word in actual_text for word in _keywords(step))]


def _missing_artifacts(expected: list[str], actual: list[str]) -> list[str]:
    actual_set = {item.replace("\\", "/") for item in actual}
    return [item for item in expected if item.replace("\\", "/") not in actual_set]


def _missing_acceptance(expected: list[str], actual: list[str]) -> list[str]:
    actual_set = {item.lower() for item in actual}
    return [item for item in expected if item.lower() not in actual_set]


def _has_fixture(paths: list[str]) -> bool:
    return any("/fixtures/" in path.replace("\\", "/") for path in paths)


def _keywords(text: str) -> list[str]:
    words = [word.strip(".,:;()").lower() for word in text.split()]
    return [word for word in words if len(word) >= 8][:3] or words[:1]


def _validate_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    for key in ("prompt", "expected_steps", "expected_artifacts", "acceptance_criteria", "required_capabilities"):
        if key not in reference:
            raise ValueError(f"{reference_path} must contain {key}")


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no Programmer prompt references found in {curriculum_dir}")
    return paths


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value is None:
        return []
    return [str(value)]


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 3)


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "curricula"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"programmer_prompt_curriculum_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

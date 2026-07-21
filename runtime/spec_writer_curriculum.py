"""SpecWriter curriculum evaluator for teacher-reference projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from .project_benchmark import analyze_project


REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"


def run_spec_writer_curriculum(
    *,
    root: Path,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    cases = [run_curriculum_case(root=root, reference_path=path) for path in _reference_paths(curriculum_dir)]
    report = _report(cases, curriculum_dir=curriculum_dir)
    if write:
        out_dir = root / "artifacts" / "curricula"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"spec_writer_curriculum_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_curriculum_case(*, root: Path, reference_path: Path) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_teacher_reference(reference_path, reference)
    project_dir = _resolve_project_dir(root, reference_path, reference)
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"SpecWriter curriculum pass for {reference_path.parent.name}",
        project_report=project_report,
        until_artifact_type="TechnicalSpec",
    )
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    actual = _actual_spec(spec)
    score = _score_spec(dict(reference.get("expected_spec", {})), actual)
    backlog = _improvement_backlog(score)
    passed = score["score"] >= 0.9 and not backlog
    return {
        "case": reference_path.parent.name,
        "project_dir": project_dir.as_posix(),
        "status": "ok" if passed else "needs_improvement",
        "score": score,
        "teacher_reference": {
            "reference_quality": reference.get("reference_quality"),
            "teacher_profile": reference.get("teacher_profile"),
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
        },
        "actual": actual,
        "teacher_review": _teacher_review(reference.get("teacher_review", {}), backlog),
        "improvement_backlog": backlog,
    }


def _actual_spec(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}))
    ranked = list(contract.get("ranked_candidates", []))
    return {
        "artifact_type": spec.get("artifact_type"),
        "role": spec.get("role"),
        "candidate": contract.get("candidate"),
        "ranked_first": dict(ranked[0]).get("source") if ranked else None,
        "ranked_candidates": _sources(ranked, key="source"),
        "source_evidence": _sources(spec.get("source_evidence", []), key="source"),
        "acceptance_sources": _sources(spec.get("acceptance_criteria", []), key="source"),
        "traceability_sources": _sources(spec.get("traceability_table", []), key="source"),
        "non_goals": _strings(spec.get("non_goals", [])),
        "constraints": _strings(spec.get("constraints", [])),
        "forbidden_actions_observed": _strings(spec.get("forbidden_actions_observed", [])),
        "handoff_role": dict(spec.get("implementation_handoff", {})).get("recommended_role"),
    }


def _score_spec(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    spec_producer = producer_for_artifact_type("TechnicalSpec")
    plan_producer = producer_for_artifact_type("ImplementationPlan")
    checks = {
        "artifact_is_technical_spec": actual.get("artifact_type") == "TechnicalSpec" and actual.get("role") == spec_producer,
        "candidate_matches": actual.get("candidate") == expected.get("candidate"),
        "candidate_ranked_first": actual.get("ranked_first") == actual.get("candidate"),
        "required_ranked_candidates_covered": _expected_covered(expected.get("ranked_candidates", []), actual.get("ranked_candidates", [])),
        "required_source_evidence_covered": _expected_covered(expected.get("source_evidence", []), actual.get("source_evidence", [])),
        "required_acceptance_sources_covered": _expected_covered(expected.get("acceptance_sources", []), actual.get("acceptance_sources", [])),
        "required_non_goals_covered": _expected_covered(expected.get("required_non_goals", []), actual.get("non_goals", [])),
        "forbidden_candidates_absent": _forbidden_absent(expected.get("forbidden_candidates", []), [actual.get("candidate")]),
        "no_forbidden_actions_observed": not actual.get("forbidden_actions_observed"),
        "handoff_role_targets_next_configured_producer": actual.get("handoff_role") == plan_producer,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {"score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)), "checks": checks, "warnings": warnings}


def _report(cases: list[dict[str, Any]], *, curriculum_dir: Path) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    milestone = "SpecWriter Curriculum External-3 v0.1" if "external" in curriculum_dir.name else "SpecWriter Curriculum Local-3 v0.1"
    return {
        "status": "ok" if passed == len(cases) else "needs_improvement",
        "milestone": milestone,
        "generated_at": _now(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "score": _ratio(sum(case["score"]["score"] for case in cases), len(cases)),
            "backlog_items": sum(len(case["improvement_backlog"]) for case in cases),
        },
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "facts_and_judgments_scored_separately": True,
            "automatic_code_changes_from_own_output": False,
            "implementer_tester_reviewer_not_in_scope": True,
        },
        "cases": cases,
    }


def _improvement_backlog(score: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "SPEC_WRITER_GAP", "check": warning} for warning in score["warnings"]]


def _teacher_review(value: Any, backlog: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "project_condition": value.get("project_condition", ""),
        "expected_spec_behavior": _strings(value.get("expected_spec_behavior", [])),
        "known_risks": _strings(value.get("known_risks", [])),
        "status": "watch" if backlog else "covered_by_current_run",
    }


def _validate_teacher_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    if not isinstance(reference.get("expected_spec"), dict):
        raise ValueError(f"{reference_path} must contain expected_spec object")


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no SpecWriter teacher references found in {curriculum_dir}")
    return paths


def _resolve_project_dir(root: Path, reference_path: Path, reference: dict[str, Any]) -> Path:
    project = Path(str(reference.get("project_dir") or reference_path.parent / "source"))
    if not project.is_absolute():
        project = root / project
    if not project.is_dir():
        raise FileNotFoundError(f"curriculum project not found: {project}")
    return project.resolve()


def _sources(rows: Any, *, key: str) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(str(row.get(key)) for row in rows if isinstance(row, dict) and row.get(key))


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted(str(item) for item in value if item is not None)
    if value is None:
        return []
    return [str(value)]


def _expected_covered(expected: Any, actual: Any) -> bool:
    expected_values = _strings(expected)
    actual_text = "\n".join(_strings(actual)).lower()
    return all(item.lower() in actual_text for item in expected_values)


def _forbidden_absent(forbidden: Any, actual: Any) -> bool:
    forbidden_values = _strings(forbidden)
    actual_text = "\n".join(_strings(actual)).lower()
    return all(item.lower() not in actual_text for item in forbidden_values)


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

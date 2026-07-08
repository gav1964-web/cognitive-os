"""Architect curriculum evaluator for local teacher-reference projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_benchmark import analyze_project
from .role_skills import run_architect_skill


FACT_CATEGORIES = [
    "entrypoints",
    "capability_candidates",
    "pure_transforms",
    "hidden_orchestrators",
    "side_effects",
    "idempotency_risks",
    "minimal_extraction_plan",
]

JUDGMENT_CHECKS = [
    "chosen_option_matches",
    "best_first_candidate_in_capabilities",
    "risk_sources_covered",
    "subsystem_boundaries_covered",
    "required_non_goals_covered",
    "forbidden_capability_sources_absent",
    "source_strata_covered",
]

REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"


def run_architect_curriculum(
    *,
    root: Path,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    cases = [run_curriculum_case(root=root, reference_path=path) for path in _reference_paths(curriculum_dir)]
    report = _report(cases)
    if write:
        out_dir = root / "artifacts" / "curricula"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"architect_curriculum_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_curriculum_case(*, root: Path, reference_path: Path) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_teacher_reference(reference_path, reference)
    project_dir = _resolve_project_dir(root, reference_path, reference)
    outputs = analyze_project(project_dir)
    project_report = outputs["project_map_report"]
    adr = run_architect_skill(
        goal=f"Architect curriculum pass for {reference_path.parent.name}",
        project_report=project_report,
    )
    actual = {
        "facts": _actual_facts(project_report),
        "judgments": _actual_judgments(adr),
    }
    fact_score = _score_facts(dict(reference.get("facts", {})), actual["facts"])
    judgment_score = _score_judgments(dict(reference.get("judgments", {})), actual["judgments"])
    improvement_backlog = _improvement_backlog(fact_score, judgment_score)
    teacher_review = _teacher_review(reference.get("teacher_review", {}), improvement_backlog)
    passed = fact_score["recall"] >= 0.9 and fact_score["precision"] >= 0.75 and judgment_score["score"] >= 0.8
    return {
        "case": reference_path.parent.name,
        "project_dir": project_dir.as_posix(),
        "status": "ok" if passed else "needs_improvement",
        "fact_score": fact_score,
        "judgment_score": judgment_score,
        "teacher_reference": {
            "reference_quality": reference.get("reference_quality"),
            "teacher_profile": reference.get("teacher_profile"),
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
        },
        "actual": actual,
        "teacher_review": teacher_review,
        "improvement_backlog": improvement_backlog,
    }


def _actual_facts(project_report: dict[str, Any]) -> dict[str, list[str]]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    return {
        "entrypoints": _strings(summary.get("entrypoints", [])),
        "capability_candidates": sorted(
            set(
                _strings(capabilities.get("atomic_reusable_capabilities", []))
                + _sources(plan.get("capabilities_to_extract", []), key="capability")
            )
        ),
        "pure_transforms": _function_sources(capabilities.get("pure_transforms", [])),
        "hidden_orchestrators": _function_sources(readiness.get("hidden_orchestrators", [])),
        "side_effects": _side_effects(readiness),
        "idempotency_risks": _sources(readiness.get("idempotency_risks", []), key="target"),
        "minimal_extraction_plan": _sources(plan.get("capabilities_to_extract", []), key="capability"),
    }


def _actual_judgments(adr: dict[str, Any]) -> dict[str, Any]:
    source_strata = dict(adr.get("source_strata", {}))
    return {
        "chosen_option_id": dict(adr.get("chosen_option", {})).get("id"),
        "capability_sources": _sources(adr.get("capability_model", []), key="source"),
        "risk_sources": sorted(set(str(row.get("source")) for row in adr.get("risks", []) if row.get("source"))),
        "subsystem_boundary_ids": _subsystem_boundary_refs(adr.get("subsystem_boundaries", [])),
        "non_goals": _strings(adr.get("non_goals", [])),
        "source_strata": {
            "active_core": _source_strata_paths(source_strata.get("active_core", [])),
            "legacy_noise": _source_strata_paths(source_strata.get("legacy_noise", [])),
            "context_only": _source_strata_paths(source_strata.get("context_only", [])),
            "packaged_copy": _source_strata_paths(source_strata.get("packaged_copy", [])),
        },
    }


def _score_facts(expected: dict[str, Any], actual: dict[str, list[str]]) -> dict[str, Any]:
    categories = []
    total_expected = 0
    total_hits = 0
    total_false_positive = 0
    for category in FACT_CATEGORIES:
        expected_values = _strings(expected.get(category, []))
        actual_values = _strings(actual.get(category, []))
        hits = _hits(expected_values, actual_values)
        misses = [item for item in expected_values if item not in hits]
        false_positives = _false_positives(expected_values, actual_values)
        total_expected += len(expected_values)
        total_hits += len(hits)
        total_false_positive += len(false_positives)
        categories.append(
            {
                "category": category,
                "expected": len(expected_values),
                "actual": len(actual_values),
                "hits": hits,
                "misses": misses,
                "false_positives": false_positives[:8],
                "recall": _ratio(len(hits), len(expected_values)),
                "precision": _ratio(len(actual_values) - len(false_positives), len(actual_values)),
            }
        )
    actual_total = sum(len(actual.get(category, [])) for category in FACT_CATEGORIES)
    return {
        "recall": _ratio(total_hits, total_expected),
        "precision": _ratio(actual_total - total_false_positive, actual_total),
        "categories": categories,
    }


def _score_judgments(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "chosen_option_matches": actual.get("chosen_option_id") == expected.get("chosen_option_id"),
        "best_first_candidate_in_capabilities": expected.get("best_first_candidate") in actual.get("capability_sources", []),
        "risk_sources_covered": _any_expected_matches(expected.get("risk_sources", []), actual.get("risk_sources", [])),
        "subsystem_boundaries_covered": _expected_covered(
            expected.get("subsystem_boundary_ids", []),
            actual.get("subsystem_boundary_ids", []),
        ),
        "required_non_goals_covered": _expected_covered(expected.get("required_non_goals", []), actual.get("non_goals", [])),
        "forbidden_capability_sources_absent": _forbidden_absent(
            expected.get("forbidden_capability_sources", []),
            actual.get("capability_sources", []),
        ),
        "source_strata_covered": _source_strata_covered(
            expected.get("required_source_strata", {}),
            actual.get("source_strata", {}),
        ),
    }
    return {
        "score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": [name for name, ok in checks.items() if not ok],
    }


def _report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    fact_recall = _ratio(sum(case["fact_score"]["recall"] for case in cases), len(cases))
    fact_precision = _ratio(sum(case["fact_score"]["precision"] for case in cases), len(cases))
    judgment_score = _ratio(sum(case["judgment_score"]["score"] for case in cases), len(cases))
    return {
        "status": "ok" if passed == len(cases) else "needs_improvement",
        "milestone": "Architect Curriculum Local-3 v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "fact_recall": fact_recall,
            "fact_precision": fact_precision,
            "judgment_score": judgment_score,
            "backlog_items": sum(len(case["improvement_backlog"]) for case in cases),
            "tooling_targets": _tooling_target_summary(cases),
        },
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "facts_and_judgments_scored_separately": True,
            "automatic_code_changes_from_own_output": False,
        },
        "cases": cases,
    }


def _validate_teacher_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    if not isinstance(reference.get("facts"), dict):
        raise ValueError(f"{reference_path} must contain facts object")
    if not isinstance(reference.get("judgments"), dict):
        raise ValueError(f"{reference_path} must contain judgments object")


def _improvement_backlog(fact_score: dict[str, Any], judgment_score: dict[str, Any]) -> list[dict[str, Any]]:
    backlog = []
    for row in fact_score["categories"]:
        if row["misses"]:
            backlog.append({"type": "FACT_RECALL_GAP", "category": row["category"], "items": row["misses"]})
        if row["false_positives"]:
            backlog.append({"type": "FACT_PRECISION_GAP", "category": row["category"], "items": row["false_positives"]})
    for warning in judgment_score["warnings"]:
        backlog.append({"type": "ARCHITECT_JUDGMENT_GAP", "check": warning})
    return backlog


def _teacher_review(value: Any, backlog: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    targets = _strings(value.get("tooling_improvement_targets", []))
    return {
        "project_condition": value.get("project_condition", ""),
        "expected_architect_behavior": _strings(value.get("expected_architect_behavior", [])),
        "known_noise": _strings(value.get("known_noise", [])),
        "tooling_improvement_targets": targets,
        "target_status": [
            {
                "target": target,
                "status": "watch" if backlog else "covered_by_current_run",
                "reason": "case has score backlog" if backlog else "no scoring gap for this teacher reference",
            }
            for target in targets
        ],
    }


def _tooling_target_summary(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        review = dict(case.get("teacher_review", {}))
        for target in review.get("tooling_improvement_targets", []):
            target_text = str(target)
            counts[target_text] = counts.get(target_text, 0) + 1
    return dict(sorted(counts.items()))


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no teacher references found in {curriculum_dir}")
    return paths


def _resolve_project_dir(root: Path, reference_path: Path, reference: dict[str, Any]) -> Path:
    project = Path(str(reference.get("project_dir") or reference_path.parent / "source"))
    if not project.is_absolute():
        project = root / project
    if not project.is_dir():
        raise FileNotFoundError(f"curriculum project not found: {project}")
    return project.resolve()


def _function_sources(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(
        str(row.get("capability") or f"{row.get('path')}:{row.get('name')}")
        for row in rows
        if isinstance(row, dict) and (row.get("capability") or row.get("path"))
    )


def _sources(rows: Any, *, key: str) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(str(row.get(key)) for row in rows if isinstance(row, dict) and row.get(key))


def _side_effects(readiness: dict[str, Any]) -> list[str]:
    values = set()
    for row in readiness.get("idempotency_risks", []):
        if isinstance(row, dict):
            values.update(str(item) for item in row.get("side_effects", []) if item)
    for row in readiness.get("process_boundary_candidates", []):
        if isinstance(row, dict):
            values.update(str(item) for item in row.get("reasons", []) if item in {"filesystem", "network", "subprocess"})
    return sorted(values)


def _subsystem_boundary_refs(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("id"):
            refs.add(str(row["id"]))
        refs.update(str(item) for item in row.get("owned_files", []) if item)
    return sorted(refs)


def _source_strata_paths(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return sorted(str(row.get("path")) for row in rows if isinstance(row, dict) and row.get("path"))


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False, sort_keys=True)]
    if value is None:
        return []
    return [str(value)]


def _hits(expected: list[str], actual: list[str]) -> list[str]:
    actual_text = "\n".join(actual).lower()
    return [item for item in expected if item.lower() in actual_text]


def _false_positives(expected: list[str], actual: list[str]) -> list[str]:
    if not expected:
        return actual
    lowered = [item.lower() for item in expected]
    return [item for item in actual if not any(expected_item in item.lower() for expected_item in lowered)]


def _expected_covered(expected: Any, actual: Any) -> bool:
    expected_values = _strings(expected)
    actual_text = "\n".join(_strings(actual)).lower()
    return all(item.lower() in actual_text for item in expected_values)


def _any_expected_matches(expected: Any, actual: Any) -> bool:
    expected_values = _strings(expected)
    actual_text = "\n".join(_strings(actual)).lower()
    return not expected_values or any(item.lower() in actual_text for item in expected_values)


def _forbidden_absent(forbidden: Any, actual: Any) -> bool:
    forbidden_values = _strings(forbidden)
    actual_text = "\n".join(_strings(actual)).lower()
    return all(item.lower() not in actual_text for item in forbidden_values)


def _source_strata_covered(expected: Any, actual: Any) -> bool:
    if not isinstance(expected, dict) or not expected:
        return True
    if not isinstance(actual, dict):
        return False
    for kind, expected_paths in expected.items():
        if not _expected_covered(expected_paths, actual.get(str(kind), [])):
            return False
    return True


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)

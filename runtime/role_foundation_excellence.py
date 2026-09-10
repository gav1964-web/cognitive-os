"""9.5 readiness scoring for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architect_curriculum import run_architect_curriculum
from .spec_writer_curriculum import run_spec_writer_curriculum
from tools.github_architect_probe import run_probe as run_github_architect
from tools.github_spec_writer_probe import run_probe as run_github_spec_writer


TARGET_SCORE = 9.5


def run_role_foundation_excellence(
    *,
    root: Path,
    github_dir: Path,
    target_score: float = TARGET_SCORE,
) -> dict[str, Any]:
    runs = {
        "architect_local": run_architect_curriculum(root=root, curriculum_dir=root / "curricula" / "architect_local_3"),
        "architect_external": run_architect_curriculum(root=root, curriculum_dir=root / "curricula" / "architect_external_local_3"),
        "architect_github": run_github_architect(root=root, projects_dir=github_dir, label="foundation_excellence_architect"),
        "spec_local": run_spec_writer_curriculum(root=root, curriculum_dir=root / "curricula" / "spec_writer_local_3"),
        "spec_external": run_spec_writer_curriculum(root=root, curriculum_dir=root / "curricula" / "spec_writer_external_local_3"),
        "spec_github": run_github_spec_writer(root=root, projects_dir=github_dir, label="foundation_excellence_spec_writer"),
    }
    roles = {
        "project_analyzer": _score_project_analyzer(runs, target_score=target_score),
        "architect": _score_architect(runs, target_score=target_score),
        "spec_writer": _score_spec_writer(runs, target_score=target_score),
    }
    return {
        "status": "ok" if all(row["target_met"] for row in roles.values()) else "needs_work",
        "milestone": "Role Foundation Excellence 9.5",
        "generated_at": _now(),
        "target_score": target_score,
        "roles": roles,
        "summary": {
            "average_score": _average(row["score"] for row in roles.values()),
            "below_target": [role for role, row in roles.items() if not row["target_met"]],
        },
        "invariants": {
            "scope": "Project Analyzer -> Architect -> SpecWriter only",
            "teacher_reference_is_ground_truth": False,
            "llm_required_for_score": False,
            "downstream_roles_not_scored": True,
        },
        "source_reports": _compact_source_reports(runs),
    }


def _score_project_analyzer(runs: dict[str, Any], *, target_score: float) -> dict[str, Any]:
    local = runs["architect_local"]
    external = runs["architect_external"]
    github = runs["architect_github"]
    local_summary = dict(local.get("summary", {}))
    external_summary = dict(external.get("summary", {}))
    github_summary = dict(github.get("summary", {}))
    fact_recall = _average([local_summary.get("fact_recall"), external_summary.get("fact_recall")])
    fact_precision = _average([local_summary.get("fact_precision"), external_summary.get("fact_precision")])
    github_quality = float(github_summary.get("avg_quality_score") or 0.0)
    coverage = _coverage_score(github_summary, github.get("project_count"))
    backlog = _backlog_pressure(local_summary, external_summary)
    factual_floor = min(
        _curriculum_project_analyzer_floor(local),
        _curriculum_project_analyzer_floor(external),
        _github_project_analyzer_floor(github),
        coverage,
    )
    score = _ten_point(factual_floor)
    improvement = []
    if fact_precision < 0.95:
        improvement.append("raise teacher-reference fact precision without hiding useful extra evidence")
    if fact_recall < 0.97:
        improvement.append("improve missed project facts in local/external curricula")
    if coverage < 1.0:
        improvement.append("restore GitHub analyzer coverage and read-only guarantees")
    if backlog > 0:
        improvement.append("close teacher-reference analyzer backlog instead of accepting MVP pass")
    return _role_result(
        score,
        target_score=target_score,
        metrics={
            "fact_recall": fact_recall,
            "fact_precision": fact_precision,
            "github_quality": github_quality,
            "github_coverage": coverage,
            "worst_case_floor": factual_floor,
            "backlog_is_score_blocking": False,
            "teacher_backlog_pressure": backlog,
        },
        improvement=improvement,
    )


def _score_architect(runs: dict[str, Any], *, target_score: float) -> dict[str, Any]:
    local = dict(runs["architect_local"].get("summary", {}))
    external = dict(runs["architect_external"].get("summary", {}))
    github = dict(runs["architect_github"].get("summary", {}))
    judgment = _average([local.get("judgment_score"), external.get("judgment_score")])
    fact_recall = _average([local.get("fact_recall"), external.get("fact_recall")])
    fact_precision = _average([local.get("fact_precision"), external.get("fact_precision")])
    github_quality = float(github.get("avg_quality_score") or 0.0)
    backlog = _backlog_pressure(local, external)
    component_floor = min(
        _curriculum_architect_floor(runs["architect_local"]),
        _curriculum_architect_floor(runs["architect_external"]),
        _github_quality_floor(runs["architect_github"]),
    )
    score = _ten_point(component_floor)
    improvement = []
    if judgment < 0.98:
        improvement.append("improve architecture choices against teacher-corrected references")
    if fact_precision < 0.95:
        improvement.append("tighten evidence selection feeding ADR capability/risk choices")
    if backlog > 0:
        improvement.append("close architect curriculum backlog before calling the role 9.5-level")
    return _role_result(
        score,
        target_score=target_score,
        metrics={
            "judgment": judgment,
            "fact_recall": fact_recall,
            "fact_precision": fact_precision,
            "github_quality": github_quality,
            "worst_case_floor": component_floor,
            "teacher_backlog_pressure": backlog,
        },
        improvement=improvement,
    )


def _score_spec_writer(runs: dict[str, Any], *, target_score: float) -> dict[str, Any]:
    local = dict(runs["spec_local"].get("summary", {}))
    external = dict(runs["spec_external"].get("summary", {}))
    github = dict(runs["spec_github"].get("summary", {}))
    curriculum = _average([local.get("score"), external.get("score")])
    github_quality = float(github.get("avg_quality_score") or 0.0)
    semantic = _semantic_score(github)
    strong_ratio = _strong_ratio(github)
    hygiene = _github_hygiene(github)
    component_floor = min(
        _curriculum_spec_floor(runs["spec_local"]),
        _curriculum_spec_floor(runs["spec_external"]),
        _github_spec_semantic_floor(runs["spec_github"]),
        hygiene,
    )
    score = _ten_point(component_floor)
    improvement = []
    if semantic < 0.95:
        improvement.append("increase strong/acceptable semantic target quality on GitHub corpus")
    if strong_ratio < 0.75:
        improvement.append("raise the share of strong SpecWriter first-slice targets")
    if hygiene < 1.0:
        improvement.append("remove needs_review, forbidden sources or source mutation from SpecWriter probes")
    return _role_result(
        score,
        target_score=target_score,
        metrics={
            "curriculum": curriculum,
            "github_quality": github_quality,
            "semantic_target_quality": semantic,
            "semantic_strong_ratio": strong_ratio,
            "github_hygiene": hygiene,
            "worst_case_floor": component_floor,
        },
        improvement=improvement,
    )


def _role_result(score: float, *, target_score: float, metrics: dict[str, Any], improvement: list[str]) -> dict[str, Any]:
    return {
        "score": score,
        "target_met": score >= target_score,
        "metrics": metrics,
        "improvement": improvement,
    }


def _semantic_score(summary: dict[str, Any]) -> float:
    strong = int(summary.get("semantic_strong") or 0)
    acceptable = int(summary.get("semantic_acceptable") or 0)
    suspicious = int(summary.get("semantic_suspicious") or 0)
    poor = int(summary.get("semantic_poor") or 0)
    count = strong + acceptable + suspicious + poor
    if count == 0:
        return 0.0
    return round((strong + acceptable * 0.55 + suspicious * 0.2) / count, 4)


def _strong_ratio(summary: dict[str, Any]) -> float:
    strong = int(summary.get("semantic_strong") or 0)
    acceptable = int(summary.get("semantic_acceptable") or 0)
    suspicious = int(summary.get("semantic_suspicious") or 0)
    poor = int(summary.get("semantic_poor") or 0)
    count = strong + acceptable + suspicious + poor
    return round(strong / count, 4) if count else 0.0


def _backlog_pressure(*summaries: dict[str, Any]) -> float:
    items = sum(int(summary.get("backlog_items") or 0) for summary in summaries)
    return min(1.0, round(items / 20.0, 4))


def _github_hygiene(summary: dict[str, Any]) -> float:
    count = int(summary.get("ok") or 0) + int(summary.get("needs_review") or 0) + int(summary.get("blocked_no_safe_candidate") or 0)
    if count == 0:
        return 0.0
    penalties = int(summary.get("needs_review") or 0) + int(summary.get("forbidden_sources") or 0) + int(summary.get("source_code_changes") or 0)
    return max(0.0, round(1.0 - penalties / count, 4))


def _curriculum_project_analyzer_floor(report: dict[str, Any]) -> float:
    scores = []
    for case in report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        fact = dict(case.get("fact_score", {}))
        scores.append(min(float(fact.get("recall") or 0.0), float(fact.get("precision") or 0.0)))
    return round(min(scores), 4) if scores else 0.0


def _curriculum_architect_floor(report: dict[str, Any]) -> float:
    scores = []
    for case in report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        fact = dict(case.get("fact_score", {}))
        judgment = dict(case.get("judgment_score", {}))
        scores.append(
            min(
                float(fact.get("recall") or 0.0),
                float(fact.get("precision") or 0.0),
                float(judgment.get("score") or 0.0),
            )
        )
    return round(min(scores), 4) if scores else 0.0


def _curriculum_spec_floor(report: dict[str, Any]) -> float:
    scores = [
        float(dict(case.get("score", {})).get("score") or 0.0)
        for case in report.get("cases", []) or []
        if isinstance(case, dict)
    ]
    return round(min(scores), 4) if scores else 0.0


def _github_quality_floor(report: dict[str, Any]) -> float:
    scores = [
        float(case.get("quality_score") or 0.0)
        for case in report.get("cases", []) or []
        if isinstance(case, dict)
    ]
    return round(min(scores), 4) if scores else 0.0


def _github_project_analyzer_floor(report: dict[str, Any]) -> float:
    scores = []
    for case in report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        if case.get("status") == "blocked_ok":
            scores.append(float(case.get("quality_score") or 0.0))
            continue
        summary = dict(case.get("summary", {}))
        scores.append(min(float(case.get("quality_score") or 0.0), float(summary.get("project_report_quality") or 0.0)))
    return round(min(scores), 4) if scores else 0.0


def _github_spec_semantic_floor(report: dict[str, Any]) -> float:
    scores = []
    for case in report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        if case.get("status") == "blocked_ok":
            scores.append(1.0)
            continue
        semantic = dict(case.get("semantic_target_quality", {}))
        scores.append(min(float(case.get("quality_score") or 0.0), float(semantic.get("score") or 0.0) / 100.0))
    return round(min(scores), 4) if scores else 0.0


def _coverage_score(summary: dict[str, Any], project_count: Any) -> float:
    count = int(project_count or 0)
    if count == 0:
        return 0.0
    ok = int(summary.get("ok") or 0) + int(summary.get("blocked_no_safe_candidate") or 0)
    bad = int(summary.get("forbidden_capability_sources") or 0) + int(summary.get("source_code_changes") or 0)
    return max(0.0, round((ok - bad) / count, 4))


def _compact_source_reports(runs: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {
            "status": report.get("status"),
            "project_count": report.get("project_count"),
            "summary": report.get("summary", {}),
        }
        for name, report in runs.items()
    }


def _ten_point(value: float) -> float:
    return round(max(0.0, min(10.0, value * 10.0)), 2)


def _average(values: Any) -> float:
    items = [float(value) for value in values if value is not None]
    return round(sum(items) / len(items), 4) if items else 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

"""Qualify discovered projects through Analyzer and recognition before role-chain runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_recognition import recognize_project
from .role_foundation_field_trial import _primary_language_scope
from .role_project_analysis import analyze_role_project


def qualify_project_corpus(
    *,
    root: Path,
    projects_dir: Path,
    expected_stratum: str | None = None,
    minimum_qualified: int | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run only the inexpensive authoritative stages needed for corpus admission."""
    cases = [
        _qualify_project(
            root=root,
            project_dir=project_dir,
            expected_stratum=expected_stratum,
            profile=profile,
        )
        for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir())
    ]
    counts = {
        status: sum(case["qualification_status"] == status for case in cases)
        for status in ("qualified", "needs_review", "rejected")
    }
    required = len(cases) if minimum_qualified is None else max(1, int(minimum_qualified))
    qualified_projects = [
        case["project"] for case in cases if case["qualification_status"] == "qualified"
    ]
    return {
        "artifact_type": "ProjectRecognitionCorpusReport",
        "schema_version": "project_recognition_corpus.v1",
        "status": "ready" if counts["qualified"] >= required else "needs_replacement",
        "expected_stratum": expected_stratum,
        "minimum_qualified": required,
        "replacement_count": max(0, required - counts["qualified"]),
        "qualified_projects": qualified_projects,
        "project_count": len(cases),
        "summary": counts,
        "cases": cases,
    }


def _qualify_project(
    *,
    root: Path,
    project_dir: Path,
    expected_stratum: str | None,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    language_scope = _primary_language_scope(project_dir)
    if language_scope.get("status") != "in_scope":
        return {
            "project": project_dir.name,
            "qualification_status": "rejected",
            "reasons": ["primary_language_out_of_scope"],
            "language_scope": language_scope,
        }

    project_report = analyze_role_project(
        root=root,
        project_dir=project_dir,
        goal=f"Qualify project type for {project_dir.name}",
    )["project_map_report"]
    recognition = recognize_project(
        project=project_dir.name,
        project_report=project_report,
        profile=profile,
    )
    classification = dict(recognition.get("classification") or {})
    actual_stratum = str(classification.get("project_stratum") or "unknown_new_archetype")
    reasons = list(recognition.get("ambiguity_reasons") or [])
    if expected_stratum and actual_stratum != expected_stratum:
        reasons.append(f"expected_stratum:{expected_stratum};actual:{actual_stratum}")
    if recognition.get("status") != "recognized":
        qualification_status = "needs_review"
    elif reasons:
        qualification_status = "rejected"
    else:
        qualification_status = "qualified"

    answers = dict(project_report.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    return {
        "project": project_dir.name,
        "qualification_status": qualification_status,
        "reasons": reasons,
        "language_scope": language_scope,
        "domain_profile": dict(scope.get("domain_profile") or {}),
        "project_shape": dict(project_report.get("source_health") or {}).get("project_shape"),
        "recognition": recognition,
    }

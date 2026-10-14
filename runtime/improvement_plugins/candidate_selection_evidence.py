"""Recover ordinary-route evidence for a shadow-selected challenger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def attach_ordinary_challenger_evidence(
    control: dict[str, Any], treatment: dict[str, Any], challenger: str,
    *, project_dir: Path | None = None,
) -> dict[str, Any]:
    ranked = _control_ranked_candidates(control)
    ordinary = next(
        (dict(row) for row in ranked if str(row.get("source") or "") == challenger),
        {},
    )
    quality = dict(treatment.get("selected_candidate_quality") or {})
    selection = dict(quality.get("selection_evidence") or {})
    if not ordinary:
        readiness = _target_dependency_readiness(project_dir, challenger)
        if not readiness:
            return treatment
        rules = _target_viability_rules(project_dir, challenger, control)
        selection.update({
            "dependency_readiness": readiness,
            "evidence_route": "static_target_dependency_analysis",
        })
        if rules:
            selection["ranking_reasons"] = [
                *list(selection.get("ranking_reasons") or []),
                f"execution cost requires reselection: {', '.join(rules)}",
            ]
        return {
            **treatment,
            "selected_candidate_quality": {**quality, "selection_evidence": selection},
        }
    source = dict(ordinary.get("evidence") or {})
    selection.update({
        "ranked_score": ordinary.get("score"),
        "kind": ordinary.get("kind"),
        "ranking_reasons": list(ordinary.get("reasons") or []),
        "dependency_readiness": dict(source.get("dependency_readiness") or {}),
        "evidence_route": "ordinary_full_candidate_ranking",
    })
    return {
        **treatment,
        "selected_candidate_quality": {**quality, "selection_evidence": selection},
    }


def _target_dependency_readiness(
    project_dir: Path | None, target: str,
) -> dict[str, Any]:
    if project_dir is None:
        return {}
    relative, separator, symbol = target.rpartition(":")
    if not separator or not relative.endswith(".py") or not symbol:
        return {}
    from runtime.source_dependency_readiness import source_dependency_readiness

    return source_dependency_readiness(project_dir, relative, symbol)


def _target_viability_rules(
    project_dir: Path | None, target: str, control: dict[str, Any],
) -> list[str]:
    if project_dir is None:
        return []
    from runtime.first_slice_viability import first_slice_viability
    from runtime.role_source_context import build_source_context
    from runtime.source_target_evidence import source_target_evidence

    report = _control_artifact_content(control, "project_map_report")
    evidence = build_source_context(
        project_root=str(project_dir), project_report=report, sources=[target],
        function_scoped_dependencies=True,
    ).get(target) or source_target_evidence(project_dir, target)
    profile = first_slice_viability(
        target, evidence, knowledge_rule=_control_knowledge_rule(control),
    )
    return [str(row.get("rule_id") or "") for row in profile.get("matched_rules") or [] if row.get("rule_id")]


def _control_knowledge_rule(control: dict[str, Any]) -> str:
    content = _control_artifact_content(control, "architecture_decision")
    return str(dict(content.get("first_slice_contract") or {}).get("knowledge_rule") or "")


def _control_artifact_content(control: dict[str, Any], key: str) -> dict[str, Any]:
    artifact = dict(dict(control.get("artifacts") or {}).get(key) or {})
    path = Path(str(artifact.get("path") or ""))
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("content") or payload)


def _control_ranked_candidates(control: dict[str, Any]) -> list[dict[str, Any]]:
    from runtime.technical_spec_builder import _rank_extraction_candidates

    artifact = dict(dict(control.get("artifacts") or {}).get("technical_spec") or {})
    path = Path(str(artifact.get("path") or ""))
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _rank_extraction_candidates(list(payload.get("source_evidence") or []))

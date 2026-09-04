from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.self_development_prospective_detection import (
    ProspectiveDetectionError,
    load_prospective_detection_policy,
    run_prospective_detection,
)


ROOT = Path(__file__).resolve().parents[2]


def _policy() -> dict:
    return {
        "schema_version": "self_development_prospective_detection.v1",
        "status": "active",
        "evidence_cutoff": "2026-08-30T00:00:00+00:00",
        "source_directory": "artifacts/project_development",
        "source_glob": "project_development_*.json",
        "maturity_matrix": "matrix.json",
        "allowed_project_types": ["library_pure_transform"],
        "systematic_rule_ids": ["recognition_gap"],
        "minimum_independent_projects": 3,
        "target": "knowledge/role_knowledge/self_development_lessons.json",
        "role_scope_by_rule": {
            "recognition_gap": ["project_analyzer", "researcher", "architect"],
        },
        "invariants": {
            "pre_cutoff_evidence_forbidden": True,
            "cross_project_independence_required": True,
            "source_apply": False,
            "promotion_applied": False,
            "candidate_requires_future_holdout": True,
        },
    }


def _workspace(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts" / "project_development"
    directory.mkdir(parents=True)
    (tmp_path / "knowledge" / "role_knowledge").mkdir(parents=True)
    (tmp_path / "matrix.json").write_text(json.dumps({
        "cells": [{
            "applicable": True,
            "maturity": "mature",
            "project_stratum": "library_pure_transform",
        }],
    }), encoding="utf-8")


def _write_report(
    root: Path,
    index: int,
    project: str,
    *,
    generated_at: str = "2026-08-31T00:00:00+00:00",
    rule_id: str = "recognition_gap",
    subject: str = "ambiguous_project_identity",
) -> None:
    path = root / "artifacts" / "project_development" / f"project_development_{index}.json"
    path.write_text(json.dumps({
        "artifact_type": "ProjectDevelopmentRun",
        "generated_at": generated_at,
        "project": project,
        "status": "controlled_stop",
        "recognition": {"classification": {
            "project_stratum": "library_pure_transform",
        }},
        "diagnosis": {"issues": [{
            "rule_id": rule_id,
            "category": "classification",
            "subject": subject,
        }]},
    }), encoding="utf-8")


def test_current_corpus_waits_for_strictly_new_evidence() -> None:
    report = run_prospective_detection(root=ROOT, write=False)

    assert report["status"] == "waiting_for_evidence"
    assert report["candidate_count"] == 0
    assert report["audit"]["post_cutoff_files"] >= 10
    assert report["audit"]["pre_cutoff_excluded"] == 75
    assert all(report["checks"].values())


def test_three_new_independent_projects_create_shadow_l0_candidate(tmp_path: Path) -> None:
    _workspace(tmp_path)
    for index, project in enumerate(("alpha", "beta", "gamma"), start=1):
        _write_report(tmp_path, index, project)

    report = run_prospective_detection(root=tmp_path, policy=_policy(), write=False)

    assert report["status"] == "candidate_detected"
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    proposal = candidate["dossier"]["proposal"]
    assert candidate["independent_project_count"] == 3
    assert proposal["classification"]["class"] == "L0"
    assert proposal["impact_map"]["project_types"] == ["library_pure_transform"]
    assert candidate["dossier"]["admissions"]["propose"]["status"] == "allowed"
    assert candidate["dossier"]["admissions"]["sandbox"]["status"] == "blocked"
    assert candidate["dossier"]["admissions"]["promote"]["status"] == "blocked"


def test_repeated_reports_for_one_project_do_not_fake_independence(tmp_path: Path) -> None:
    _workspace(tmp_path)
    for index in range(1, 4):
        _write_report(tmp_path, index, "same-project")

    report = run_prospective_detection(root=tmp_path, policy=_policy(), write=False)

    assert report["status"] == "waiting_for_evidence"
    assert report["candidate_count"] == 0
    assert report["watchlist_count"] == 1
    watch = report["watchlist"][0]
    assert watch["independent_project_count"] == 1
    assert watch["additional_independent_projects_required"] == 2
    assert watch["projects"] == ["same-project"]
    assert len(watch["evidence"]) == 1


def test_pre_cutoff_and_non_systematic_reports_are_excluded(tmp_path: Path) -> None:
    _workspace(tmp_path)
    _write_report(
        tmp_path, 1, "old", generated_at="2026-08-29T23:59:59+00:00"
    )
    _write_report(tmp_path, 2, "unrelated", rule_id="weak_contracts")
    _write_report(tmp_path, 3, "new")

    report = run_prospective_detection(root=tmp_path, policy=_policy(), write=False)

    assert report["candidate_count"] == 0
    assert report["audit"]["pre_cutoff_excluded"] == 1
    assert report["audit"]["non_systematic_issue"] == 1
    assert report["audit"]["eligible_project_reports"] == 2
    assert report["audit"]["eligible_reports_without_systematic_issue"] == 1


def test_derived_handoff_signal_uses_same_three_project_gate(tmp_path: Path) -> None:
    _workspace(tmp_path)
    policy = _policy()
    policy["systematic_rule_ids"].append("role_handoff_gap")
    policy["derived_signals"] = [{
        "rule_id": "role_handoff_gap",
        "category": "handoff",
        "subject": "selected_target_alignment",
        "when": [{"path": "role_chain_handoff.status", "equals": "needs_replanning"}],
    }]
    policy["role_scope_by_rule"]["role_handoff_gap"] = ["architect", "spec_writer"]
    for index, project in enumerate(("alpha", "beta", "gamma"), start=1):
        _write_report(tmp_path, index, project, rule_id="weak_contracts")
        path = tmp_path / "artifacts" / "project_development" / f"project_development_{index}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["role_chain_handoff"] = {"status": "needs_replanning"}
        path.write_text(json.dumps(payload), encoding="utf-8")

    report = run_prospective_detection(root=tmp_path, policy=policy, write=False)

    assert report["status"] == "candidate_detected"
    assert report["candidates"][0]["signature"].startswith("role_handoff_gap:")


def test_classification_contradiction_uses_same_independence_gate(tmp_path: Path) -> None:
    _workspace(tmp_path)
    policy = _policy()
    policy["systematic_rule_ids"].append("classification_contradiction")
    policy["role_scope_by_rule"]["classification_contradiction"] = [
        "project_analyzer",
        "researcher",
        "architect",
        "tester",
    ]
    for index, project in enumerate(("alpha", "beta", "gamma"), start=1):
        _write_report(
            tmp_path,
            index,
            project,
            rule_id="classification_contradiction",
            subject="owned_contract_vs_project_identity",
        )

    report = run_prospective_detection(root=tmp_path, policy=policy, write=False)

    assert report["status"] == "candidate_detected"
    candidate = report["candidates"][0]
    assert candidate["signature"].startswith("classification_contradiction:")
    assert candidate["independent_project_count"] == 3
    assert candidate["dossier"]["proposal"]["classification"]["class"] == "L0"
    assert candidate["dossier"]["admissions"]["sandbox"]["status"] == "blocked"
    assert candidate["dossier"]["admissions"]["promote"]["status"] == "blocked"


def test_policy_rejects_disabled_temporal_boundary(tmp_path: Path) -> None:
    policy = copy.deepcopy(_policy())
    policy["invariants"]["pre_cutoff_evidence_forbidden"] = False
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ProspectiveDetectionError, match="invariants are incomplete"):
        load_prospective_detection_policy(str(path))


def test_current_policy_is_fail_closed() -> None:
    policy = load_prospective_detection_policy(
        str(ROOT / "config" / "self_development_prospective_detection.json")
    )

    assert policy["minimum_independent_projects"] == 3
    assert policy["invariants"]["pre_cutoff_evidence_forbidden"] is True
    assert policy["invariants"]["promotion_applied"] is False

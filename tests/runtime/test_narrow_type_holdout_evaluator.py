from runtime.narrow_type_holdout_evaluator import evaluate_narrow_type_holdout


ROLES = ["project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer"]
STRATA = ["cli_local_tool", "library_pure_transform"]


def _evaluation():
    return {
        "cells": [
            {
                "role_id": role,
                "project_stratum": project_type,
                "score": 9.8,
                "promotion_eligible": True,
                "blind_project_count": 3,
                "blind_source_lineages": ["blind-a", "blind-b"],
                "acquisition_source_lineages": ["train-a", "train-b"],
                "lineage_disjoint": True,
                "evidence_gaps": [],
            }
            for project_type in STRATA
            for role in ROLES
        ],
        "sources": [{"path": "blind-a.json", "blind": True}, {"path": "blind-b.json", "blind": True}],
    }


def _pipeline():
    return {
        "report_path": "role-pipeline.json",
        "summary": {"role_chain": {"handoff_loss_count": 0, "minimum_interaction_score": 1.0}},
    }


def test_holdout_evidence_requires_explicit_stub_audit():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(), role_pipeline_report=_pipeline()
    )

    assert report["status"] == "evidence_required"
    assert report["failed_checks"] == ["generated_stub_gate"]


def test_holdout_evidence_passes_with_bound_zero_stub_audit():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(),
        role_pipeline_report=_pipeline(),
        stub_audit={
            "artifact_type": "GeneratedFunctionStubAudit",
            "status": "passed",
            "generated_stub_count": 0,
        },
    )

    assert report["status"] == "passed"
    assert report["checks"]["lineage_disjoint"] is True


def test_holdout_evidence_rejects_shared_lineage():
    evaluation = _evaluation()
    evaluation["cells"][0]["lineage_disjoint"] = False
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation,
        role_pipeline_report=_pipeline(),
        stub_audit={
            "artifact_type": "GeneratedFunctionStubAudit",
            "status": "passed",
            "generated_stub_count": 0,
        },
    )

    assert report["status"] == "evidence_required"
    assert report["checks"]["lineage_disjoint"] is False

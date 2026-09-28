from runtime.narrow_type_holdout_evaluator import evaluate_narrow_type_holdout
from runtime.framework_plugin_role_semantics import artifact_digest
from runtime.narrow_type_evidence_binding import content_digest
from runtime.role_project_type_evaluation_policy import load_role_project_type_policy
import pytest


ROLES = ["project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer"]
STRATA = ["cli_local_tool", "library_pure_transform"]
PROVENANCE = {
    "evaluation": {"verified": True},
    "role_pipeline": {"verified": True},
    "stub_audit": {"verified": True},
    "blind_reports": [
        {"verified": True, "content_digest": "sha256:a"},
        {"verified": True, "content_digest": "sha256:b"},
    ],
}


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


def _semantic_evidence():
    artifacts = {
        "project_map_report": {"artifact_type": "ProjectMapReport"},
        "architecture_decision": {"artifact_type": "ArchitectureDecision"},
        "technical_spec": {"artifact_type": "TechnicalSpec"},
    }
    return {
        "artifact_type": "NarrowTypeRoleSemanticEvidence",
        "schema_version": "narrow_type_role_semantic_evidence.v2",
        "status": "passed",
        "evaluation_split": "holdout",
        "checks": {"holdout_independent_owners_per_stratum": True},
        "cases": [
            {
                "project_stratum": project_type,
                "source_owner": f"owner-{project_type}",
                "role_scores": {role: 9.8 for role in ROLES},
                "role_artifacts": artifacts,
                "role_artifact_digests": {
                    name: artifact_digest(value) for name, value in artifacts.items()
                },
                "development_change_evaluated": True,
            }
            for project_type in STRATA
        ],
    }


def test_holdout_evidence_requires_explicit_stub_audit():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(), role_pipeline_report=_pipeline(), input_provenance=PROVENANCE,
        semantic_evidence=_semantic_evidence(),
    )

    assert report["status"] == "evidence_required"
    assert report["failed_checks"] == [
        "generated_stub_gate", "stub_audit_covers_holdout", "blind_inputs_durable"
    ]


@pytest.mark.parametrize('invalid', [float('inf'), float('nan'), 10.1, True])
def test_holdout_rejects_invalid_cell_and_semantic_scores(invalid):
    evaluation = _evaluation()
    evaluation['cells'][0]['score'] = invalid
    semantic = _semantic_evidence()
    semantic['cases'][0]['role_scores']['project_analyzer'] = invalid
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation, role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE, semantic_evidence=semantic,
    )
    assert report['checks']['scores_at_promotion_target'] is False
    assert report['checks']['semantic_role_quality'] is False


def test_holdout_binds_evaluation_and_policy_and_rejects_duplicate_cells():
    evaluation = _evaluation()
    evaluation['cells'].append(dict(evaluation['cells'][0]))
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation, role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE, semantic_evidence=_semantic_evidence(),
    )
    assert report['checks']['all_required_cells_present'] is False
    assert report['evaluation_digest'] == content_digest(evaluation)
    assert report['policy_digest'] == content_digest(load_role_project_type_policy())


def test_holdout_rejects_structural_only_v1_semantic_scores():
    semantic = _semantic_evidence()
    semantic["schema_version"] = "narrow_type_role_semantic_evidence.v1"

    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(), role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE, semantic_evidence=semantic,
    )

    assert report["status"] == "evidence_required"
    assert "semantic_role_quality" in report["failed_checks"]


def test_holdout_evidence_passes_with_bound_zero_stub_audit():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(),
        role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE,
        stub_audit={
            "artifact_type": "GeneratedFunctionStubAudit",
            "status": "passed",
            "generated_stub_count": 0,
            "report_digests": {"blind-a.json": "sha256:a", "blind-b.json": "sha256:b"},
        },
        semantic_evidence=_semantic_evidence(),
    )

    assert report["status"] == "passed"
    assert report["checks"]["lineage_disjoint"] is True


def test_holdout_evidence_rejects_shared_lineage():
    evaluation = _evaluation()
    evaluation["cells"][0]["lineage_disjoint"] = False
    report = evaluate_narrow_type_holdout(
        evaluation=evaluation,
        role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE,
        stub_audit={
            "artifact_type": "GeneratedFunctionStubAudit",
            "status": "passed",
            "generated_stub_count": 0,
            "report_digests": {"blind-a.json": "sha256:a", "blind-b.json": "sha256:b"},
        },
        semantic_evidence=_semantic_evidence(),
    )

    assert report["status"] == "evidence_required"
    assert report["checks"]["lineage_disjoint"] is False


def test_holdout_evidence_rejects_partial_stub_audit_coverage():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(),
        role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE,
        stub_audit={
            "artifact_type": "GeneratedFunctionStubAudit",
            "status": "passed",
            "generated_stub_count": 0,
            "report_digests": {"blind-a.json": "sha256:a"},
        },
        semantic_evidence=_semantic_evidence(),
    )

    assert report["status"] == "evidence_required"
    assert report["checks"]["stub_audit_covers_holdout"] is False
    assert report["checks"]["blind_inputs_durable"] is False


def test_holdout_rejects_self_declared_semantic_booleans():
    report = evaluate_narrow_type_holdout(
        evaluation=_evaluation(),
        role_pipeline_report=_pipeline(),
        input_provenance=PROVENANCE,
        semantic_evidence={
            "status": "passed",
            "role_artifacts_auditable": True,
            "project_development_evaluated": True,
        },
    )

    assert report["checks"]["semantic_role_quality"] is False
    assert report["checks"]["role_artifacts_auditable"] is False
    assert report["checks"]["project_development_evaluated"] is False

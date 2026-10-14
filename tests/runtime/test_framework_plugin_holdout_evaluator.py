from runtime.framework_plugin_holdout_evaluator import evaluate_framework_plugin_holdout
from runtime.framework_plugin_readiness import REQUIRED_ROLES


def _evaluation() -> dict:
    return {"cells": [{
        "role_id": role,
        "project_stratum": "framework_plugin_build",
        "score": 9.8,
        "maturity": "mature",
        "evidence_gaps": [],
        "blind_project_count": 3,
    } for role in REQUIRED_ROLES]}


def _report(project: str) -> dict:
    artifacts = {
        "project_map_report": {"project": project},
        "architecture_decision": {"project": project},
        "technical_spec": {"project": project},
    }
    from runtime.framework_plugin_role_semantics import artifact_digest
    return {
        "status": "ok",
        "cases": [{
            "project": project,
            "status": "ok",
            "failed_checks": [],
            "executor": {
                "executor_status": "ok",
                "executable_acceptance": "passed",
                "callable_harness_count": 1,
            },
            "generated_function_stub_admission": {"status": "passed"},
            "role_semantic_quality": {
                "status": "passed",
                "role_scores": {
                    "project_analyzer": 9.8,
                    "architect": 9.8,
                    "spec_writer": 9.8,
                },
                "development_change_evaluated": True,
            },
            "role_artifacts": artifacts,
            "role_artifact_digests": {
                name: artifact_digest(value) for name, value in artifacts.items()
            },
        }],
    }


def test_framework_holdout_evidence_binds_all_gates() -> None:
    projects = ["a__one", "b__two", "c__three"]
    reports = [_report(project) for project in projects]
    digests = {f"/reports/{project}.json": f"sha256:{index:064x}" for index, project in enumerate(projects, 1)}
    evidence = evaluate_framework_plugin_holdout(
        selection={
            "status": "local_corpus_sufficient",
            "selection_digest": "sha256:selection",
            "acquisition": [{}, {}, {}],
            "holdout": [
                {"project": project, "owner": project.split("__")[0]}
                for project in projects
            ],
            "checks": {"owner_disjoint": True, "content_disjoint": True},
        },
        evaluation=_evaluation(),
        holdout_reports=reports,
        report_digests=digests,
        stub_audit={
            "status": "passed",
            "generated_stub_count": 0,
            "report_digests": digests,
        },
        role_regression={"status": "passed", "regression_count": 0},
        input_digests={f"input-{index}": "sha256:" + "a" * 64 for index in range(7)},
    )

    assert evidence["status"] == "passed"
    assert evidence["failed_checks"] == []
    assert evidence["holdout_provenance"]["source_lineages"] == 3
    assert evidence["role_scores"]["project_analyzer"] == 9.8
    assert evidence["matrix_role_scores"]["project_analyzer"] == 9.8


def test_framework_holdout_rejects_verification_only_semantics() -> None:
    projects = ["a__one", "b__two", "c__three"]
    reports = [_report(project) for project in projects]
    reports[0]["cases"][0]["role_semantic_quality"]["development_change_evaluated"] = False
    digests = {f"/{project}.json": f"sha256:{index:064x}" for index, project in enumerate(projects, 1)}

    evidence = evaluate_framework_plugin_holdout(
        selection={
            "status": "local_corpus_sufficient",
            "acquisition": [{}, {}, {}],
            "holdout": [{"project": project, "owner": project.split("__")[0]} for project in projects],
            "checks": {"owner_disjoint": True, "content_disjoint": True},
        },
        evaluation=_evaluation(), holdout_reports=reports, report_digests=digests,
        stub_audit={"status": "passed", "generated_stub_count": 0, "report_digests": digests},
        role_regression={"status": "passed", "regression_count": 0},
        input_digests={f"input-{index}": "sha256:" + "a" * 64 for index in range(7)},
    )

    assert evidence["status"] == "evidence_required"
    assert "project_development_evaluated" in evidence["failed_checks"]

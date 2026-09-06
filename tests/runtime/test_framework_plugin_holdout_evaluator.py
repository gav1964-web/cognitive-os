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

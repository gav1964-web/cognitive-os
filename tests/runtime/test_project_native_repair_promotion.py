import json
from pathlib import Path

from runtime.project_native_repair_promotion import promote_native_repair_patterns


def _fixture(root: Path) -> Path:
    catalog = root / "knowledge/role_knowledge/project_native_failure_repair_patterns.json"
    catalog.parent.mkdir(parents=True)
    patterns = []
    for index in range(3):
        report_path = root / f"report-{index}.json"
        report_path.write_text(json.dumps({
            "status": "experiment_validated",
            "experiment": {
                "status": "verified",
                "source_invariant": {"unchanged": True},
                "project_native_verification": {
                    "status": "passed",
                    "targeted_replay": {"status": "passed"},
                    "regression_suite": {"status": "passed"},
                },
            },
            "validated_memory": {"status": "validated"},
        }), encoding="utf-8")
        patterns.append({
            "id": f"pattern-{index}",
            "failure_kind": f"failure-{index}",
            "validated_evidence": {
                "project": f"project-{index}",
                "project_development_report": report_path.name,
            },
            "promotion_ready": False,
            "promotion_blockers": ["transaction"],
        })
    catalog.write_text(json.dumps({
        "schema_version": "project_native_failure_repair_patterns.v1",
        "promotion_policy": {
            "status": "threshold_met_awaiting_explicit_promotion",
            "minimum_project_native_transformations": 3,
            "minimum_independent_lineages": 2,
            "minimum_transformation_subtypes": 3,
        },
        "patterns": patterns,
    }), encoding="utf-8")
    matrix = root / "matrix.json"
    matrix.write_text(json.dumps({"cells": [
        {
            "project_stratum": "library_pure_transform",
            "role_id": role,
            "project_native_transformation_count": 3,
            "maturity": "mature",
            "evidence_gaps": [],
        }
        for role in ("project_analyzer", "architect", "spec_writer", "implementer", "tester", "reviewer")
    ]}), encoding="utf-8")
    return matrix


def test_promotion_transaction_activates_catalog_only_after_all_gates(tmp_path: Path):
    matrix = _fixture(tmp_path)
    report = promote_native_repair_patterns(
        root=tmp_path,
        matrix_path=matrix,
        explicit_approval=True,
        regression_passed=True,
        config_doctor_passed=True,
        line_limit_passed=True,
    )

    catalog = json.loads((tmp_path / "knowledge/role_knowledge/project_native_failure_repair_patterns.json").read_text())
    assert report["status"] == "promoted"
    assert catalog["promotion_policy"]["status"] == "active"
    assert all(row["promotion_ready"] for row in catalog["patterns"])


def test_promotion_transaction_leaves_catalog_unchanged_when_gate_fails(tmp_path: Path):
    matrix = _fixture(tmp_path)
    catalog = tmp_path / "knowledge/role_knowledge/project_native_failure_repair_patterns.json"
    before = catalog.read_bytes()
    report = promote_native_repair_patterns(
        root=tmp_path,
        matrix_path=matrix,
        explicit_approval=True,
        regression_passed=False,
        config_doctor_passed=True,
        line_limit_passed=True,
    )

    assert report["status"] == "blocked"
    assert report["failed_checks"] == ["regression_tests"]
    assert catalog.read_bytes() == before

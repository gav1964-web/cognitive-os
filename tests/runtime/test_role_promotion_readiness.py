from __future__ import annotations

import json
from pathlib import Path

from runtime.role_promotion_policy import load_role_promotion_policy
from runtime.role_promotion_readiness import build_role_promotion_readiness


def test_role_promotion_policy_loads_first_four_roles() -> None:
    policy = load_role_promotion_policy()

    assert policy["first_four_roles"]["project_analyzer"]["target_score"] == 9.7
    assert policy["scope_boundary"]["foundation_roles_1_3"]["applies_to"] == "Python-owned boundary"
    assert "unseen_project_types" in policy["score_bands"]["9_7"]["required_evidence"]
    assert "runtime_rebuild_corpus" in policy["score_bands"]["9_7"]["required_evidence"]


def test_role_promotion_readiness_blocks_small_foundation_report(tmp_path: Path) -> None:
    report_path = _write_report(tmp_path / "field.json", [_case("demo")])

    report = build_role_promotion_readiness(
        tmp_path,
        [report_path],
        evidence=["regression_tests", "config_doctor", "line_limit_check"],
    )

    assert report["status"] == "needs_work"
    assert report["roles"]["project_analyzer"]["score_ceiling"] == 9.2
    assert "minimum_projects:9_7" in report["roles"]["architect"]["gaps"]
    assert "missing_check:implementation_plan_present" in report["roles"]["implementer"]["gaps"]


def test_role_promotion_readiness_passes_complete_synthetic_evidence(tmp_path: Path) -> None:
    cases = [_case(f"project_{index}", include_implementer=True) for index in range(80)]
    report_path = _write_report(tmp_path / "wide.json", cases)
    corpus_path = _write_corpus_report(tmp_path / "corpus.json", source_evidence_score=80.0, probes=80)

    report = build_role_promotion_readiness(
        tmp_path,
        [report_path, corpus_path],
        evidence=[
            "regression_tests",
            "config_doctor",
            "line_limit_check",
            "no_source_changes",
            "unseen_project_types",
        ],
    )

    assert report["status"] == "ready_for_9_7"
    assert report["summary"]["ready_for_9_7"] == 4
    assert report["roles"]["spec_writer"]["score_ceiling"] == 9.7


def test_role_promotion_readiness_caps_foundation_roles_on_runtime_source_evidence(tmp_path: Path) -> None:
    cases = [_case(f"project_{index}", include_implementer=True) for index in range(80)]
    report_path = _write_report(tmp_path / "wide.json", cases)
    corpus_path = _write_corpus_report(tmp_path / "corpus.json", source_evidence_score=70.0, probes=80)

    report = build_role_promotion_readiness(
        tmp_path,
        [report_path, corpus_path],
        evidence=[
            "regression_tests",
            "config_doctor",
            "line_limit_check",
            "no_source_changes",
            "unseen_project_types",
        ],
    )

    analyzer = report["roles"]["project_analyzer"]
    assert analyzer["score_ceiling"] == 8.75
    assert analyzer["metrics"]["runtime_source_evidence_ratio"] == 0.875
    assert "runtime_source_evidence_below_target" in analyzer["gaps"]
    assert report["roles"]["implementer"]["score_ceiling"] == 9.7


def test_role_promotion_readiness_blocks_foundation_report_below_calibrated_target(tmp_path: Path) -> None:
    cases = [_foundation_case(f"project_{index}") for index in range(80)]
    report_path = tmp_path / "foundation.json"
    report_path.write_text(
        json.dumps(
            {
                "artifact_type": "RoleFoundationFieldTrialReport",
                "status": "needs_work",
                "summary": {"source_code_changes": 0},
                "calibration": {"calibrated_readiness_min_score": 9.0},
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )

    report = build_role_promotion_readiness(
        tmp_path,
        [report_path],
        evidence=[
            "regression_tests",
            "config_doctor",
            "line_limit_check",
            "no_source_changes",
            "unseen_project_types",
        ],
    )

    assert report["status"] == "needs_work"
    assert report["roles"]["project_analyzer"]["score_ceiling"] == 9.0
    assert "calibrated_readiness_below_target" in report["roles"]["spec_writer"]["gaps"]


def test_role_promotion_readiness_reads_single_foundation_pipeline_report(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.json"
    path.write_text(
        json.dumps(
            {
                "kind": "role_foundation_pipeline",
                "status": "ok",
                "project": "demo",
                "score": _case("demo")["score"],
            }
        ),
        encoding="utf-8",
    )

    report = build_role_promotion_readiness(
        tmp_path,
        [path],
        evidence=["regression_tests", "config_doctor", "line_limit_check"],
    )

    analyzer = report["roles"]["project_analyzer"]
    assert analyzer["metrics"]["checks"]["project_map_report_present"] == 1
    assert analyzer["metrics"]["semantic_score"] == 9.7


def test_role_promotion_readiness_reads_implementer_curriculum(tmp_path: Path) -> None:
    path = tmp_path / "curriculum.json"
    payload = {
        "milestone": "Implementer Curriculum Local-3 v0.1",
        "summary": {"source_code_changes": 0},
        "cases": [
            {
                "case": "demo",
                "status": "ok",
                "score": {"score": 0.96},
                "actual": {
                    "artifact_type": "ImplementationPlan",
                    "candidate": "main.py:run",
                    "binding_candidate": "main.py:run",
                    "binding_status": "bound_to_extraction_contract",
                    "patch_scope": ["main.py:run"],
                    "writable_scope": ["main.py:run"],
                    "rollback_files": ["main.py"],
                    "verification_commands": ["python -m pytest -q"],
                    "executor_handoff_type": "ExecutorHandoff",
                    "acceptance_mapping_count": 2,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_role_promotion_readiness(
        tmp_path,
        [path],
        evidence=["regression_tests", "config_doctor", "line_limit_check"],
    )

    implementer = report["roles"]["implementer"]
    assert "missing_check:implementation_plan_present" not in implementer["gaps"]
    assert "missing_semantic_check:rollback_plan_present" not in implementer["gaps"]


def _write_report(path: Path, cases: list[dict]) -> Path:
    payload = {
        "artifact_type": "RoleFoundationBenchmark",
        "status": "ok",
        "summary": {"source_code_changes": 0},
        "cases": cases,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_corpus_report(path: Path, *, source_evidence_score: float, probes: int) -> Path:
    payload = {
        "kind": "github_rebuild_corpus",
        "status": "ok",
        "summary": {
            "source_evidence_score": source_evidence_score,
            "module_import_probes": probes,
            "http_probes": 0,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _case(project: str, *, include_implementer: bool = False) -> dict:
    checks = {
        "project_map_report_present": True,
        "project_report_has_answers": True,
        "project_map_report_quality_passed": True,
        "foundation_semantic_quality_passed": True,
        "adr_present": True,
        "adr_has_chosen_option": True,
        "adr_has_traceability": True,
        "adr_quality_passed": True,
        "architect_red_team_passed": True,
        "spec_present": True,
        "spec_has_requirements": True,
        "spec_has_acceptance": True,
        "spec_has_traceability": True,
        "spec_has_extraction_contract": True,
        "spec_writer_red_team_passed": True,
    }
    if include_implementer:
        checks.update(
            {
                "implementation_plan_present": True,
                "implementation_plan_quality_passed": True,
                "contract_binding_present": True,
                "executor_handoff_present": True,
                "verification_commands_present": True,
            }
        )
    return {
        "project": project,
        "status": "ok",
        "score": {
            "passed": True,
            "artifact_score": 1.0,
            "checks": checks,
            "foundation_semantic_quality": {
                "role_scores": {
                    "project_analyzer": 9.7,
                    "architect": 9.7,
                    "spec_writer": 9.7,
                    "implementer": 9.6,
                },
                "checks": {
                    "project_analyzer": _semantic(
                        "purpose_avoids_marketing_blurb",
                        "generic_profile_not_masking_library_domain",
                        "evidence_summary_is_source_backed",
                        "minimal_extraction_plan_is_actionable",
                    ),
                    "architect": _semantic(
                        "domain_profile_carried_to_architecture",
                        "first_slice_not_generic_when_domain_cues_exist",
                        "spec_target_is_within_architect_slice",
                        "source_context_has_multiple_refs",
                    ),
                    "spec_writer": _semantic(
                        "io_contract_shapes_specific",
                        "requirements_and_acceptance_are_implementable",
                        "traceability_links_sources_to_acceptance",
                        "implementation_handoff_bounded",
                    ),
                    "implementer": _semantic(
                        "contract_binding_is_source_backed",
                        "patch_scope_is_bounded",
                        "acceptance_mapping_present",
                        "rollback_plan_present",
                    ),
                },
            },
        },
    }


def _foundation_case(project: str) -> dict:
    return {
        "project": project,
        "status": "ok",
        "project_min_score": 10.0,
        "selected_extraction_candidate": "src/app.py:handle",
        "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0},
        "artifacts": {"project_map_report": {}, "architecture_decision": {}, "technical_spec": {}},
        "semantic_quality": {
            "status": "ok",
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0},
            "checks": {
                "project_analyzer": _semantic(
                    "purpose_avoids_marketing_blurb",
                    "generic_profile_not_masking_library_domain",
                    "evidence_summary_is_source_backed",
                    "minimal_extraction_plan_is_actionable",
                ),
                "architect": _semantic(
                    "domain_profile_carried_to_architecture",
                    "first_slice_not_generic_when_domain_cues_exist",
                    "spec_target_is_within_architect_slice",
                    "source_context_has_multiple_refs",
                ),
                "spec_writer": _semantic(
                    "io_contract_shapes_specific",
                    "requirements_and_acceptance_are_implementable",
                    "traceability_links_sources_to_acceptance",
                    "implementation_handoff_bounded",
                ),
            },
        },
    }


def _semantic(*codes: str) -> list[dict]:
    return [{"code": code, "passed": True} for code in codes]

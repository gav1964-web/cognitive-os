from __future__ import annotations

from tests.runtime.role_project_type_evaluation_helpers import *

def test_published_role_score_is_not_overwritten_by_internal_semantic_score(tmp_path: Path) -> None:
    source = tmp_path / "foundation.json"
    source.write_text(json.dumps({"cases": [{
        **_case("scientific-project", 9.2, 9.0),
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": load_role_project_type_policy()["classification_version"],
            "project_stratum": "scientific_compute",
        },
        "role_scores": {"project_analyzer": 9.2, "architect": 9.0, "spec_writer": 8.8},
        "semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0},
        },
    }]}), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    assert _cell(report, "project_analyzer", "scientific_compute")["score"] == 9.2
    assert _cell(report, "architect", "scientific_compute")["score"] == 9.0
    assert _cell(report, "spec_writer", "scientific_compute")["score"] == 8.8


def test_one_transformation_subtype_cannot_mature_a_broad_stratum(tmp_path: Path) -> None:
    sources = []
    for report_index in range(2):
        source = tmp_path / f"cli-{report_index}.json"
        source.write_text(json.dumps({
            "source_lineage": f"corpus-{report_index}",
            "cases": [{
                **_case(f"cli-{report_index}-{case_index}", 10.0, 10.0),
                "role_scores": {"implementer": 10.0, "tester": 10.0, "reviewer": 10.0},
                "project_classification": {
                    "schema_version": "role_project_classification.v1",
                    "policy_version": load_role_project_type_policy()["classification_version"],
                    "project_stratum": "cli_local_tool",
                    "project_subtype": "argv_json_stdout_json",
                },
                "programmer_evidence": {"transformation_evaluated": True},
            } for case_index in range(3)],
        }), encoding="utf-8")
        sources.append(source)

    report = build_role_project_type_evaluation(
        root=tmp_path, report_paths=sources, blind_report_paths=sources
    )

    cell = _cell(report, "tester", "cli_local_tool")
    assert cell["maturity"] == "usable"
    assert cell["transformation_subtype_count"] == 1
    assert "minimum_transformation_subtypes" in cell["evidence_gaps"]


def test_derived_transformation_benchmarks_do_not_claim_project_type_maturity(
    tmp_path: Path,
) -> None:
    sources = []
    for report_index in range(2):
        source = tmp_path / f"derived-{report_index}.json"
        source.write_text(json.dumps({
            "source_lineage": f"derived-corpus-{report_index}",
            "cases": [{
                **_case(f"cli-derived-{report_index}-{case_index}", 10.0, 10.0),
                "project_classification": {
                    "schema_version": "role_project_classification.v1",
                    "policy_version": load_role_project_type_policy()["classification_version"],
                    "project_stratum": "cli_local_tool",
                    "project_archetype": "derived_cli_mutation_benchmark",
                    "project_subtype": f"argv_json_stdout_json_{case_index}",
                },
                "programmer_evidence": {"transformation_evaluated": True},
            } for case_index in range(3)],
        }), encoding="utf-8")
        sources.append(source)

    report = build_role_project_type_evaluation(
        root=tmp_path, report_paths=sources, blind_report_paths=sources
    )

    cell = _cell(report, "implementer", "cli_local_tool")
    assert cell["score"] == 10.0
    assert cell["score_scope"] == "bounded_transformation_contracts"
    assert cell["maturity"] == "usable"
    assert cell["project_native_transformation_count"] == 0
    assert cell["transformation_evidence_scopes"] == ["derived_transformation_benchmark"]
    assert "minimum_project_native_transformations" in cell["evidence_gaps"]


def test_unmeasured_cells_remain_visible_in_priority_queue(tmp_path: Path) -> None:
    source = tmp_path / "measured.json"
    source.write_text(json.dumps({"cases": [_case("cli-project", 10.0, 10.0)]}), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    sdk_implementer = next(
        row for row in report["priority_queue"]
        if row["role_id"] == "implementer"
        and row["project_stratum"] == "sdk_provider_integration"
    )
    assert sdk_implementer["score"] is None
    assert sdk_implementer["maturity"] == "unmeasured"
    assert "minimum_cases" in sdk_implementer["evidence_gaps"]
    assert "unmeasured" in render_role_project_type_markdown(report)

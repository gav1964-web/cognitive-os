from __future__ import annotations

from tests.runtime.role_project_type_evaluation_helpers import *


def test_structural_downstream_scores_cannot_claim_demonstrated_maturity(
    tmp_path: Path,
) -> None:
    sources = []
    for report_index in range(2):
        source = tmp_path / f"pipeline-{report_index}.json"
        source.write_text(json.dumps({
            "source_lineage": f"corpus-{report_index}",
            "cases": [
                {
                    **_case(f"cli-project-{report_index}-{case_index}", 10.0, 10.0),
                    "role_scores": {
                        "implementer": 10.0,
                        "tester": 10.0,
                        "reviewer": 10.0,
                    },
                    "programmer_evidence": {"transformation_evaluated": False},
                }
                for case_index in range(3)
            ],
        }), encoding="utf-8")
        sources.append(source)

    report = build_role_project_type_evaluation(
        root=tmp_path,
        report_paths=sources,
        blind_report_paths=sources,
    )

    for role_id in ("implementer", "tester", "reviewer"):
        cell = _cell(report, role_id, "cli_local_tool")
        assert cell["score"] == 10.0
        assert cell["maturity"] == "usable"
        assert cell["transformation_project_count"] == 0
        assert "minimum_transformation_projects" in cell["evidence_gaps"]
        assert "minimum_independent_lineages" in cell["evidence_gaps"]


def test_numeric_case_score_does_not_hide_explicit_role_scores(tmp_path: Path) -> None:
    source = tmp_path / "transformation.json"
    source.write_text(json.dumps({
        "source_lineage": "blind-corpus",
        "cases": [{
            **_case("pure-transform", 9.8, 10.0),
            "score": 10.0,
            "programmer_evidence": {"transformation_evaluated": True},
        }],
    }), encoding="utf-8")

    report = build_role_project_type_evaluation(root=tmp_path, report_paths=[source])

    assert _cell(report, "implementer", "library_pure_transform")["score"] == 10.0

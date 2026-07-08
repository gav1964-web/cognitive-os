from __future__ import annotations

from pathlib import Path

from runtime.project_benchmark import analyze_project
from runtime.role_artifact_quality import evaluate_role_artifacts
from runtime.role_skills import (
    run_architect_skill,
    run_implementer_skill,
    run_reviewer_skill,
    run_spec_writer_skill,
    run_tester_skill,
)


ROOT = Path(__file__).resolve().parents[2]


def test_role_artifact_quality_passes_foundation_artifacts():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    project_report = analyze_project(project_dir)["project_map_report"]
    adr = run_architect_skill(goal="Extract first safe capability", project_report=project_report)
    spec = run_spec_writer_skill(architecture_decision=adr)
    implementation = run_implementer_skill(technical_spec=spec)
    test_plan = run_tester_skill(technical_spec=spec, implementation_plan=implementation)
    review = run_reviewer_skill(technical_spec=spec, implementation_plan=implementation, test_plan=test_plan)

    quality = evaluate_role_artifacts(
        {
            "architecture_decision": adr,
            "technical_spec": spec,
            "implementation_plan": implementation,
            "test_plan": test_plan,
            "review_findings": review,
        }
    )

    assert quality["passed"] is True
    assert quality["score"] == 1.0
    assert quality["warnings"] == []
    assert set(quality["results"]) == {
        "adr",
        "technical_spec",
        "implementation_plan",
        "test_plan",
        "review_findings",
    }


def test_role_artifact_quality_rejects_generic_artifacts():
    quality = evaluate_role_artifacts(
        {
            "architecture_decision": {
                "decision_summary": "Improve architecture.",
                "chosen_option": {"reason": "best practices"},
                "capability_model": [{"source": "thing"}],
                "risks": [{"description": "clean up"}],
                "traceability": [],
                "spec_writer_brief": {},
            },
            "technical_spec": {
                "requirements": [{"statement": "refactor as needed", "priority": "MUST"}],
                "acceptance_criteria": [{"criterion": "make it better", "verification": "review"}],
                "extraction_contract": {},
                "source_evidence": [],
                "traceability_table": [],
                "implementation_handoff": {},
            },
        }
    )

    assert quality["passed"] is False
    assert quality["score"] < 0.9
    assert "adr.avoids_generic_phrases" in quality["warnings"]
    assert "technical_spec.avoids_generic_phrases" in quality["warnings"]

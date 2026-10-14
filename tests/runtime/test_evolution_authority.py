from __future__ import annotations

from runtime.corpus_evaluation_factory import build_corpus_evaluation_plan
from runtime.evolution_authority import build_evolution_authority_report
from runtime.interpreter_authority import build_interpreter_decision


def _trace():
    return build_interpreter_decision(
        stage="project_analysis",
        goal="Raise narrow types with evidence",
        target="cli_local_tool",
        scope=["cli_local_tool", "library_pure_transform"],
        evidence=[{
            "reference": "evaluation.json",
            "content_digest": "sha256:" + "d" * 64,
            "kind": "role_evaluation",
        }],
        candidates=[{
            "candidate_id": "architecture",
            "next_stage": "architecture",
            "reason": "bounded narrow lane",
        }],
        selected_candidate_id="architecture",
        outcome="accepted",
        authority_source="config/role_project_type_evaluation.json",
        rule_id="narrow-python-owned",
    )


def _records():
    return [
        {
            "project": f"{project_type}-{index}",
            "project_type": project_type,
            "source_lineage": f"owner-{project_type}-{index}",
            "content_digest": "sha256:" + f"{offset + index:064x}",
            "exposure": "untouched",
        }
        for project_type, offset in (("cli_local_tool", 0), ("library_pure_transform", 100))
        for index in range(1, 6)
    ]


def test_evolution_report_does_not_claim_certification_before_holdout():
    report = build_evolution_authority_report(
        interpreter_trace=_trace(),
        role_chain_summary={"handoff_loss_count": 0, "blocked_role_return_count": 0},
        corpus_plan=build_corpus_evaluation_plan(_records()),
    )

    assert report["status"] == "ready_for_narrow_evaluation"
    assert report["next_action"] == "run_independent_narrow_type_holdout"
    assert report["product_surface"]["web_ui_is_current_milestone"] is False


def test_evolution_report_blocks_handoff_loss():
    report = build_evolution_authority_report(
        interpreter_trace=_trace(),
        role_chain_summary={"handoff_loss_count": 1, "blocked_role_return_count": 0},
        corpus_plan=build_corpus_evaluation_plan(_records()),
    )

    assert report["status"] == "blocked"
    assert "role_handoff_loss_zero" in report["failed_checks"]

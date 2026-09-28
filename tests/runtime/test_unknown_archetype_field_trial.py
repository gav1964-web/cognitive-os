from pathlib import Path

from runtime.unknown_archetype_field_trial import run_unknown_archetype_field_trial


ROOT = Path(__file__).resolve().parents[2]


def test_unknown_archetype_holdout_and_promotion_rehearsal_pass() -> None:
    report = run_unknown_archetype_field_trial(root=ROOT)

    assert report["status"] == "ok"
    assert {row["status"] for row in report["unknown_holdout"]["scenarios"]} == {"passed"}
    rehearsal = report["unknown_holdout"]["promotion_rehearsal"]
    assert rehearsal["status"] == "passed"
    assert rehearsal["candidate_before_review"] == "needs_teacher_approval"
    assert rehearsal["candidate_after_review"] == "ready_for_human_merge"
    candidate = report["unknown_holdout"]["lifecycle"]["provisional_candidates"][0]
    assert candidate["independent_lineage_count"] == 2
    assert candidate["unique_evidence_digest_count"] == 3
    assert candidate["cluster_gaps"] == []
    assert rehearsal["kb_mutations"] == 0
    assert report["summary"]["controlled_unknown_stop_count"] == 4


def test_unknown_field_trial_measures_real_known_role_chain() -> None:
    report = run_unknown_archetype_field_trial(
        root=ROOT,
        projects_dir=ROOT / "benchmarks" / "project_analyzer" / "projects",
        limit=1,
    )

    assert report["status"] == "ok"
    known = next(row for row in report["role_chain_traces"] if row["status"] != "controlled_stop")
    assert known["interaction_score"] == 1.0
    assert known["handoff_loss_count"] == 0
    assert known["selected_target"] == known["final_review_target"]
    assert report["summary"]["known_trace_count"] == 1

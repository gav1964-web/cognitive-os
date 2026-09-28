from runtime.improvement_plugins.hypothesis_evidence_planner import run
from runtime.self_improvement_plugin_foundry import resolve_plugin_requests


def _hypothesis():
    return {
        "artifact_type": "HypothesisCandidate",
        "hypothesis_id": "hc_evidence",
        "candidate_type": "evidence_collection_plan",
        "failure_class": "role_quality",
        "portable_signature": "role_quality|pure|unknown",
    }


def _report(project, *, selected="app.py:before", trained="app.py:before", delta=0.0):
    return {
        "project": project,
        "baseline": {"selected_extraction_candidate": selected},
        "trained_attempt": {"selected_extraction_candidate": trained},
        "outcome": {"score_delta": delta, "role_regressions": []},
    }


def test_planner_requests_target_discovery_when_baselines_have_no_candidate():
    result = run({
        "compiled_hypothesis": _hypothesis(),
        "evidence_reports": [_report("one", selected=None), _report("two", selected=None)],
    })

    assert result["status"] == "evidence_planned"
    assert result["plan"]["next_action"] == "discover_bounded_executable_candidates"
    assert result["plan"]["authority"] == "evidence_plan_only"
    assert result["promotion_applied"] is False


def test_planner_blocks_plugin_compilation_on_negative_transfer():
    result = run({
        "compiled_hypothesis": _hypothesis(),
        "evidence_reports": [
            _report("positive", trained="app.py:better", delta=2.0),
            _report("negative", trained="app.py:worse", delta=-1.0),
        ],
    })

    plan = result["plan"]
    assert plan["next_action"] == "resolve_cluster_contradiction"
    assert plan["observed_metrics"]["negative_transfer_count"] == 1
    assert plan["completion_gate"]["negative_transfer_count"] == 0


def test_foundry_resolves_evidence_collection_to_read_only_planner():
    report = resolve_plugin_requests([{
        "request_id": "cdr_evidence",
        "missing_capability": "bounded_hypothesis_evidence_collection",
    }], [])

    assert report["status"] == "trial_required"
    assert report["resolutions"][0]["plugin_id"] == "hypothesis_evidence_planner"


def test_planner_deduplicates_projects_and_keeps_counterexamples_separate():
    result = run({
        "compiled_hypothesis": _hypothesis(),
        "evidence_reports": [
            _report("same", trained="app.py:better", delta=2.0),
            _report("same", trained="app.py:worse", delta=-1.0),
        ],
        "counterexample_reports": [_report("control", trained="app.py:worse", delta=-2.0)],
    })

    plan = result["plan"]
    assert plan["observed_metrics"]["project_count"] == 1
    assert plan["observed_metrics"]["negative_transfer_count"] == 0
    assert plan["counterexample_projects"] == ["control"]

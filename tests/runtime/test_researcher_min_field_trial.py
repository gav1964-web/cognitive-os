import json

from runtime.researcher_min_field_trial import run_researcher_min_field_trial


def test_researcher_trial_scores_bounded_planning_contract(tmp_path):
    foundation = tmp_path / "foundation.json"
    foundation.write_text(json.dumps({"cases": [{
        "project": "cachelib",
        "artifacts": {"project_map_report": {"domain_profile": {"kind": "cache_backend_library"}}},
        "status": "ok",
    }]}), encoding="utf-8")

    report = run_researcher_min_field_trial(root=tmp_path, foundation_reports=[foundation])

    assert report["status"] == "ok"
    assert report["evidence_mode"] == "planning_only"
    assert report["cases"][0]["role_scores"]["researcher"] == 10.0
    assert report["cases"][0]["project_classification"]["project_stratum"] == "stateful_service_database"
    assert report["cases"][0]["source_code_changes"] is False

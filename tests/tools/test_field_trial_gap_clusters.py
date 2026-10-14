from __future__ import annotations

import json

from tools.field_trial_gap_clusters import build_gap_clusters


def test_field_trial_gap_clusters_prioritizes_repeated_growth_shapes(tmp_path):
    report = {
        "artifact_type": "RoleFoundationFieldTrialReport",
        "target_score": 9.5,
        "cases": [
            {
                "project": "graphql-python__graphene",
                "status": "ok",
                "project_min_score": 10.0,
                "selected_extraction_candidate": "graphene/types/schema.py:create_fields_for_type",
                "selected_candidate_quality": {
                    "score": 100,
                    "status": "strong",
                    "profiled_contract_family": False,
                },
            },
            {
                "project": "strawberry-graphql__strawberry",
                "status": "ok",
                "project_min_score": 7.7,
                "selected_extraction_candidate": "annotation.py:_resolve_evaled_type",
                "selected_candidate_quality": {
                    "score": 100,
                    "status": "strong",
                    "profiled_contract_family": False,
                },
            },
            {
                "project": "known",
                "status": "ok",
                "project_min_score": 10.0,
                "selected_extraction_candidate": "jobs.py:acquire_jobs",
                "selected_candidate_quality": {
                    "score": 100,
                    "status": "strong",
                    "profiled_contract_family": True,
                    "semantic_profile_ids": ["scheduled_job_acquisition_boundary"],
                },
            },
        ],
    }
    path = tmp_path / "foundation.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    result = build_gap_clusters([path])

    assert result["artifact_type"] == "FoundationGapClusterReport"
    assert result["gap_project_count"] == 2
    assert result["summary"]["below_target_count"] == 1
    assert result["summary"]["high_unprofiled_count"] == 2
    assert result["clusters"][0]["cluster_id"] == "graphql_type_or_schema_boundary"
    assert result["clusters"][0]["growth_action"] == "add_profile_and_target_selection_rules"

import runtime.role_foundation_field_trial as field_trial


def test_read_only_case_uses_pipeline_semantic_quality(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    semantic = {
        "status": "ok",
        "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.8},
    }
    monkeypatch.setattr(
        field_trial,
        "run_role_foundation_pipeline",
        lambda **kwargs: {
            "status": "ok",
            "score": {"foundation_semantic_quality": semantic},
            "artifacts": {
                "project_map_report": {"artifact_type": "ProjectMapReport", "status": "ok"},
                "architecture_decision": {"artifact_type": "ArchitectureDecisionRecord", "status": "ok"},
                "technical_spec": {"artifact_type": "TechnicalSpec", "status": "ok"},
            },
            "safety": {"source_code_changes": False, "llm_invoked": False},
        },
    )

    case = field_trial._run_case(root=tmp_path, project_dir=tmp_path, write=False)

    assert case["semantic_quality"] == semantic
    assert case["local_role_scores"] == semantic["role_scores"]
    assert case["role_scores"] == {
        "project_analyzer": 9.2,
        "architect": 9.0,
        "spec_writer": 8.8,
    }
    assert len(case["score_adjustments"]) == 3
    assert case["acceptance_signal"] == "not_measured"


def test_read_only_case_inspects_in_memory_artifacts(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    request = {
        "status": "required",
        "terminal": True,
        "resolution_status": "exhausted",
        "outcome": {
            "status": "exhausted",
            "authority": "architect",
            "expanded_candidate_count": 4,
            "environment_ready_candidate_count": 3,
            "candidate_viability": [],
            "semantic_qualified_candidate_count": 0,
            "selected_targets": [],
        },
    }
    pipeline_kwargs = {}

    def fake_pipeline(**kwargs):
        pipeline_kwargs.update(kwargs)
        return {
            "status": "ok",
            "score": {"foundation_semantic_quality": {"role_scores": {}}},
            "artifacts": {"technical_spec": {"path": None}},
            "artifact_contents": {
                "technical_spec": {"first_slice_reselection_request": request},
            },
        }

    monkeypatch.setattr(field_trial, "run_role_foundation_pipeline", fake_pipeline)

    case = field_trial._run_case(root=tmp_path, project_dir=tmp_path, write=False)

    assert pipeline_kwargs["include_artifact_contents"] is True
    assert case["status"] == "blocked_ok"


def test_opt_in_acceptance_lifts_unverified_score_caps(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    semantic = {"role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.8}}
    monkeypatch.setattr(field_trial, "run_role_foundation_pipeline", lambda **kwargs: {
        "status": "ok",
        "score": {"foundation_semantic_quality": semantic},
        "artifacts": {"technical_spec": {"path": None}},
        "artifact_contents": {"technical_spec": {"artifact_type": "TechnicalSpec"}},
    })
    monkeypatch.setattr(
        field_trial,
        "run_foundation_execution_feedback",
        lambda **kwargs: (
            kwargs["initial_result"],
            {"status": "passed", "acceptance_signal": "executable_callable"},
        ),
    )

    case = field_trial._run_case(
        root=tmp_path, project_dir=tmp_path, write=False, executable_acceptance=True
    )

    assert case["acceptance_signal"] == "executable_callable"
    assert case["role_scores"] == semantic["role_scores"]

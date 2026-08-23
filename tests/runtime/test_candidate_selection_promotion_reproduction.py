from runtime.improvement_plugins import candidate_selection_admission as admission


def _effect(score=9.7, signal="executable_callable"):
    return {
        "treatment": {
            "status": "ok",
            "project_min_score": score,
            "downstream_evidence": {"acceptance_signal": signal},
        },
    }


def test_holdout_reproduction_requires_untargeted_score_and_acceptance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.self_improvement_training._evaluate",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "project_min_score": 8.4,
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
            "selected_extraction_candidate": "app.py:fallback",
        },
    )

    failure = admission._holdout_reproduction_failure(tmp_path, tmp_path, _effect())

    assert failure["expected_score"] == 9.7
    assert failure["actual_score"] == 8.4
    assert failure["selected_candidate"] == "app.py:fallback"


def test_holdout_reproduction_accepts_equal_ordinary_route(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runtime.self_improvement_training._evaluate",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "project_min_score": 9.7,
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    )

    assert admission._holdout_reproduction_failure(tmp_path, tmp_path, _effect()) == {}

from runtime.self_improvement_profile_effect import evaluate_profile_effect, stage_profile_effect


def _project(tmp_path):
    (tmp_path / "admission.py").write_text(
        "def allowed_file(filename):\n"
        "    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS\n",
        encoding="utf-8",
    )
    return tmp_path


def test_effect_trial_attributes_only_same_source_profile_delta(tmp_path):
    scores = iter((9.2, 9.7))

    effect = evaluate_profile_effect(
        _project(tmp_path),
        "admission.py:allowed_file",
        lambda: {"project_min_score": next(scores), "role_scores": {"spec_writer": 9.2}},
    )

    assert effect["status"] == "confirmed_profile_effect"
    assert effect["score_delta"] == 0.5


def test_zero_effect_is_not_staged(tmp_path):
    effect = evaluate_profile_effect(
        _project(tmp_path),
        "admission.py:allowed_file",
        lambda: {"project_min_score": 9.2, "role_scores": {"spec_writer": 9.2}},
    )

    assert effect["status"] == "profile_effect_not_confirmed"
    assert stage_profile_effect(tmp_path, tmp_path / "project", effect) is None

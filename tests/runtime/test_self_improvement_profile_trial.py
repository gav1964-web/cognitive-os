from runtime.self_improvement_profile_trial import run_profile_trial
from runtime.semantic_target_profiles import matching_profiles
from runtime.semantic_target_profiles import SemanticTargetProfileError, temporary_semantic_profiles
import pytest


def test_profile_trial_is_visible_only_inside_evaluation(tmp_path):
    source = tmp_path / "integration.py"
    source.write_text(
        "async def sync_records(client, db) -> dict[str, int]:\n"
        "    try:\n"
        "        rows = await client.fetch()\n"
        "        changed = len(rows)\n"
        "        await db.commit()\n"
        "        return {'changed': changed}\n"
        "    except RuntimeError:\n"
        "        raise\n",
        encoding="utf-8",
    )
    seen = []

    def evaluate(target):
        seen.extend(matching_profiles(target))
        return {"project_min_score": 9.2, "role_scores": {"spec_writer": 9.2}, "selected_extraction_candidate": target}

    attempt = run_profile_trial(tmp_path, ["integration.py:sync_records"], evaluate)

    assert attempt["result"]["project_min_score"] == 9.2
    assert attempt["control_result"]["project_min_score"] == 9.2
    assert attempt["profile_score_delta"] == 0.0
    assert seen[0]["contract_family"] == "external_service_state_sync_boundary"
    assert not matching_profiles("integration.py:sync_records")


def test_temporary_profile_rejects_numeric_score_bonus():
    profile = {
        "id": "invalid",
        "contract_family": "invalid_boundary",
        "symbols": ["run"],
        "path_contains_any": ["app.py"],
        "input_contract": {"request": "Request"},
        "output_contract": {"result": "Result"},
        "validation_gates": ["validated"],
        "failure_modes": ["failed"],
        "score_bonus": 1,
    }

    with pytest.raises(SemanticTargetProfileError, match="numeric bonuses"):
        with temporary_semantic_profiles([profile]):
            pass


def test_profile_trial_measures_against_same_source_control(tmp_path):
    source = tmp_path / "admission.py"
    source.write_text(
        "def allowed_file(filename):\n"
        "    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS\n",
        encoding="utf-8",
    )
    calls = 0

    def evaluate(target):
        nonlocal calls
        calls += 1
        score = 9.2 if not matching_profiles(target) else 9.7
        return {"project_min_score": score, "role_scores": {"spec_writer": score}, "selected_extraction_candidate": target}

    attempt = run_profile_trial(tmp_path, ["admission.py:allowed_file"], evaluate)

    assert calls == 2
    assert attempt["control_result"]["project_min_score"] == 9.2
    assert attempt["result"]["project_min_score"] == 9.7
    assert attempt["profile_score_delta"] == 0.5


def test_profile_trial_skips_source_that_pipeline_did_not_select(tmp_path):
    _project = tmp_path / "admission.py"
    _project.write_text(
        "def allowed_file(filename):\n"
        "    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS\n",
        encoding="utf-8",
    )

    attempt = run_profile_trial(
        tmp_path,
        ["admission.py:allowed_file"],
        lambda target: {"project_min_score": 9.2, "role_scores": {}, "selected_extraction_candidate": "other.py:run"},
    )

    assert attempt is None

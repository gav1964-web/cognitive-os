from pathlib import Path

import pytest

from runtime.improvement_plugins import config_mutation
from runtime.self_improvement_plugin_cycle import run_improvement_plugin_cycle
from runtime.self_improvement_plugin_adapter import run_training_improvement_plugins
from runtime.self_improvement_plugin_loader import (
    ImprovementPluginError,
    enabled_improvement_plugins,
    load_improvement_plugin_catalog,
)


def test_improvement_plugin_catalog_enables_gated_config_promotion():
    catalog = load_improvement_plugin_catalog()
    plugins = enabled_improvement_plugins()

    assert catalog["cycle"]["runtime_patch_auto_promotion"] is False
    assert plugins[0]["id"] == "config_mutation"
    assert plugins[0]["auto_promote"] is True
    assert plugins[0]["requires_regression_cases"] is True


def test_improvement_plugin_catalog_rejects_runtime_auto_promotion(tmp_path):
    policy = tmp_path / "plugins.json"
    policy.write_text(
        '{"schema_version":"self_improvement_plugins.v1","plugins":[],"cycle":'
        '{"max_plugins_per_failure":1,"runtime_patch_auto_promotion":true}}',
        encoding="utf-8",
    )

    with pytest.raises(ImprovementPluginError, match="runtime patch auto-promotion"):
        load_improvement_plugin_catalog(str(policy))


def test_config_plugin_runs_complete_promoted_cycle(monkeypatch, tmp_path):
    captured = {}

    def evolve(**kwargs):
        captured.update(kwargs)
        return {
            "status": "passed",
            "decision": "accepted",
            "shadow": {"project_min_score": 9.7},
            "promotion": {"applied": True},
        }

    monkeypatch.setattr(
        "runtime.self_improvement_evolution_runner.evolve_diagnosed_foundation_policy",
        evolve,
    )
    result = config_mutation.run({
        "root": tmp_path,
        "project_dir": tmp_path / "weak",
        "failure_packet": {"score": 8.8},
        "diagnosis": {
            "proposed_knowledge": {"config_mutation_proposal": {"artifact_type": "ConfigMutationProposal"}}
        },
        "regression_projects": [tmp_path / "stable"],
        "requires_regression_cases": True,
        "promote": True,
    })

    assert result["status"] == "promoted"
    assert result["promotion_applied"] is True
    assert captured["promote"] is True
    assert captured["regression_projects"] == [tmp_path / "stable"]


def test_plugin_cycle_uses_autonomous_promotion_policy(monkeypatch, tmp_path: Path):
    seen = {}

    def handler(context):
        seen.update(context)
        return {"status": "promoted", "promotion_applied": True}

    monkeypatch.setattr(
        "runtime.self_improvement_plugin_cycle.load_improvement_entrypoint",
        lambda _entrypoint: handler,
    )
    result = run_improvement_plugin_cycle(
        root=tmp_path,
        project_dir=tmp_path / "weak",
        failure_packet={},
        diagnosis={},
        regression_projects=[tmp_path / "stable"],
    )

    assert result["status"] == "promoted"
    assert result["promotion_count"] == 1
    assert seen["promote"] is True


def test_config_plugin_blocks_unverified_promotion(tmp_path):
    result = config_mutation.run({
        "root": tmp_path,
        "project_dir": tmp_path / "weak",
        "failure_packet": {},
        "diagnosis": {
            "proposed_knowledge": {"config_mutation_proposal": {"artifact_type": "ConfigMutationProposal"}}
        },
        "regression_projects": [],
        "requires_regression_cases": True,
        "promote": True,
    })

    assert result == {"status": "blocked", "reason": "regression_projects_required"}


def test_promoted_plugin_treatment_becomes_training_attempt(monkeypatch, tmp_path):
    cycle = {
        "artifact_type": "SelfImprovementPluginCycleReport",
        "status": "promoted",
        "attempts": [{
            "plugin_id": "config_mutation",
            "status": "promoted",
            "promotion_applied": True,
            "evolution": {
                "shadow": {"status": "ok", "project_min_score": 9.7},
                "promotion": {"applied": True},
            },
        }],
    }
    monkeypatch.setattr(
        "runtime.self_improvement_plugin_adapter.run_improvement_plugin_cycle",
        lambda **_kwargs: cycle,
    )

    report, evolution, attempts = run_training_improvement_plugins(
        tmp_path, tmp_path / "weak", {}, {}, [tmp_path / "stable"], promote=None,
    )

    assert report["status"] == "promoted"
    assert evolution["promotion"]["applied"] is True
    assert attempts[0]["result"]["project_min_score"] == 9.7
    assert attempts[0]["parameter_changes"] == {"improvement_plugin": "config_mutation"}


def test_shadow_selected_challenger_becomes_applied_training_attempt(monkeypatch, tmp_path):
    cycle = {
        "artifact_type": "SelfImprovementPluginCycleReport",
        "status": "trial_passed",
        "attempts": [{
            "plugin_id": "candidate_selection_discriminator",
            "status": "trial_passed",
            "selected_challenger": "app.py:better",
            "promotion_applied": False,
            "evolution": {
                "shadow": {
                    "status": "ok",
                    "project_min_score": 9.6,
                    "selected_extraction_candidate": "app.py:better",
                },
                "promotion": {"applied": False},
            },
        }],
    }
    monkeypatch.setattr(
        "runtime.self_improvement_plugin_adapter.run_improvement_plugin_cycle",
        lambda **_kwargs: cycle,
    )

    _, _, attempts = run_training_improvement_plugins(
        tmp_path, tmp_path / "weak", {}, {}, [tmp_path / "stable"], promote=None,
    )

    assert attempts[0]["parameter_applied"] is True
    assert attempts[0]["plugin_evidence"]["promotion_applied"] is False
    assert attempts[0]["parameter_changes"]["spec_writer_candidate_preference"] == "app.py:better"


def test_shadow_challenger_is_chained_into_admission_context(monkeypatch, tmp_path):
    plugins = [
        {"id": "discover", "version": "1", "entrypoint": "discover:run", "auto_promote": False},
        {"id": "admit", "version": "1", "entrypoint": "admit:run", "auto_promote": True},
    ]
    seen = {}

    def load(entrypoint):
        if entrypoint == "discover:run":
            return lambda _context: {
                "status": "trial_passed", "selected_challenger": "app.py:better",
                "evolution": {
                    "baseline": {"project_min_score": 7.5},
                    "shadow": {"project_min_score": 9.7},
                },
            }
        return lambda context: seen.update(context) or {"status": "trial_passed"}

    monkeypatch.setattr("runtime.self_improvement_plugin_cycle.enabled_improvement_plugins", lambda: plugins)
    monkeypatch.setattr("runtime.self_improvement_plugin_cycle.load_improvement_entrypoint", load)
    result = run_improvement_plugin_cycle(
        root=tmp_path, project_dir=tmp_path / "weak",
        failure_packet={"selected_candidate": "app.py:weak"}, diagnosis={},
        regression_projects=[tmp_path / "stable"],
    )

    effect = seen["diagnosis"]["measured_selection_effect"]
    assert result["status"] == "trial_passed"
    assert seen["diagnosis"]["recommended_source"] == "app.py:better"
    assert effect["score_delta"] == 2.2

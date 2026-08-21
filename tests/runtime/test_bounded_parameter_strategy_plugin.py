from pathlib import Path

from runtime.improvement_plugins import bounded_parameter_strategy as plugin


def test_plugin_requires_repeated_independent_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(plugin, "_search_exhaustion_evidence", lambda _root: {"a", "b"})

    result = plugin.run(_context(tmp_path))

    assert result["status"] == "blocked"
    assert result["reason"] == "repeated_independent_evidence_required"


def test_plugin_trials_diagnostic_strategy_on_holdout(monkeypatch, tmp_path: Path):
    captured = {}
    monkeypatch.setattr(plugin, "_search_exhaustion_evidence", lambda _root: {"a", "b", "c"})
    monkeypatch.setattr(
        plugin,
        "evolve_diagnosed_foundation_policy",
        lambda **kwargs: captured.update(kwargs) or {
            "status": "passed", "promotion": {"applied": True}
        },
    )

    result = plugin.run(_context(tmp_path))

    proposal = captured["diagnosis"]["proposed_knowledge"]["config_mutation_proposal"]
    assert proposal["content"] == {"parameter_strategies": {"derived_conversion": True}}
    assert result["status"] == "promoted"
    assert result["independent_evidence_projects"] == ["a", "b", "c"]


def test_plugin_rejects_training_project_as_its_own_holdout(monkeypatch, tmp_path: Path):
    context = _context(tmp_path)
    context["project_dir"] = tmp_path / "a"
    monkeypatch.setattr(plugin, "_search_exhaustion_evidence", lambda _root: {"a", "b", "c"})

    result = plugin.run(context)

    assert result["status"] == "blocked"
    assert result["reason"] == "independent_holdout_required"


def _context(root: Path) -> dict:
    stable = root / "stable"
    stable.mkdir(exist_ok=True)
    return {
        "root": root,
        "project_dir": root / "weak",
        "failure_packet": {"detail": "ValueError: invalid literal for int()"},
        "diagnosis": {"failure_class": "executable_sample_contract"},
        "regression_projects": [stable],
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    }

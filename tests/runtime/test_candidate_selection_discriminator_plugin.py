from runtime.improvement_plugins import candidate_selection_discriminator as plugin


def _context(tmp_path):
    return {
        "root": tmp_path,
        "project_dir": tmp_path / "project",
        "failure_packet": {
            "status": "ok", "project_min_score": 8.8,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 8.8},
            "selected_candidate": "app.py:write",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
            "artifact_evidence": {
                "technical_spec": {"ranked_candidates": [
                    {"source": "app.py:write", "score": 100, "side_effects": ["memory_state"]},
                    {"source": "app.py:build", "score": 90, "side_effects": []},
                    {"source": "app.py:other", "score": 80, "side_effects": []},
                ]},
                "architecture_decision": {"first_slice": {
                    "targets": ["app.py:write", "app.py:build"],
                }},
            },
        },
        "diagnosis": {"failure_class": "side_effectful_target"},
        "plugin_config": {
            "failure_classes": ["side_effectful_target"],
            "maximum_shadow_challengers": 2,
        },
    }


def test_discriminator_returns_best_measured_shadow(monkeypatch, tmp_path):
    context = _context(tmp_path)
    results = {
        "app.py:build": {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": "app.py:build",
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
        "app.py:other": {
            "status": "ok", "project_min_score": 9.2,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.2},
            "selected_extraction_candidate": "app.py:other",
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    }
    monkeypatch.setattr(
        "runtime.self_improvement_training._evaluate",
        lambda _root, _project, **kwargs: results[kwargs["evaluation_target"]],
    )

    result = plugin.run(context)

    assert result["status"] == "trial_passed"
    assert result["selected_challenger"] == "app.py:build"
    assert result["evolution"]["shadow"]["project_min_score"] == 9.7
    assert result["promotion_applied"] is False


def test_discriminator_rejects_unmeasured_or_regressing_shadows(monkeypatch, tmp_path):
    context = _context(tmp_path)
    monkeypatch.setattr(
        "runtime.self_improvement_training._evaluate",
        lambda _root, _project, **kwargs: {
            "status": "ok", "project_min_score": 9.0,
            "role_scores": {"project_analyzer": 9.6, "architect": 9.7, "spec_writer": 9.0},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    )

    result = plugin.run(context)

    assert result["status"] == "blocked"
    assert result["reason"] == "shadow_discriminator_not_confirmed"


def test_discriminator_does_not_force_viability_rejected_candidate(monkeypatch, tmp_path):
    context = _context(tmp_path)
    ranked = context["failure_packet"]["artifact_evidence"]["technical_spec"]["ranked_candidates"]
    ranked[1]["reasons"] = ["execution cost requires reselection: external_effect_boundary"]
    context["diagnosis"]["recommended_source"] = "app.py:build"
    attempted = []

    def evaluate(_root, _project, **kwargs):
        attempted.append(kwargs["evaluation_target"])
        return {
            "status": "ok", "project_min_score": 8.8,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 8.8},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    result = plugin.run(context)

    assert result["status"] == "blocked"
    assert "app.py:build" not in attempted


def test_discriminator_confirms_convergent_emergent_candidate(monkeypatch, tmp_path):
    context = _context(tmp_path)

    def evaluate(_root, _project, **_kwargs):
        return {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": "app.py:emergent",
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    result = plugin.run(context)

    assert result["status"] == "trial_passed"
    assert result["selected_challenger"] == "app.py:emergent"
    assert result["trials"][-1]["strategy"] == "stable_reselection_convergence"


def test_discriminator_uses_bounded_reselection_and_first_slice_targets(monkeypatch, tmp_path):
    context = _context(tmp_path)
    evidence = context["failure_packet"]["artifact_evidence"]
    evidence["technical_spec"] = {
        "ranked_candidates": [{"source": "app.py:write", "score": 100}],
        "reselection": {"selected_targets": ["app.py:write", "app.py:parse"]},
    }
    evidence["architecture_decision"]["first_slice"]["targets"] = [
        "app.py:write", "app.py:normalize",
    ]
    attempted = []

    def evaluate(_root, _project, **kwargs):
        attempted.append(kwargs["evaluation_target"])
        return {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    result = plugin.run(context)

    assert result["status"] == "trial_passed"
    assert attempted == ["app.py:parse", "app.py:normalize"]


def test_discriminator_uses_non_scoring_clamp_candidate_pool(monkeypatch, tmp_path):
    context = _context(tmp_path)
    packet = context["failure_packet"]
    packet["selected_candidate"] = "app.py:failed"
    packet["artifact_evidence"] = {
        "architecture_decision": {
            "first_slice": {"targets": ["app.py:failed"]},
            "evaluation_target_clamp": {
                "mode": "evaluation_only",
                "target": "app.py:failed",
                "candidate_pool": ["app.py:build"],
            },
        },
        "technical_spec": {"ranked_candidates": [{"source": "app.py:failed"}]},
    }
    attempted = []

    def evaluate(_root, _project, **kwargs):
        attempted.append(kwargs["evaluation_target"])
        return {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    result = plugin.run(context)

    assert result["status"] == "trial_passed"
    assert result["selected_challenger"] == "app.py:build"
    assert attempted == ["app.py:build"]


def test_discriminator_probes_architect_source_pool_before_weak_first_slice(monkeypatch, tmp_path):
    context = _context(tmp_path)
    evidence = context["failure_packet"]["artifact_evidence"]
    evidence["architecture_decision"]["source_candidate_pool"] = ["pkg/core.py:build"]
    attempted = []

    def evaluate(_root, _project, **kwargs):
        attempted.append(kwargs["evaluation_target"])
        return {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    result = plugin.run(context)

    assert result["status"] == "trial_passed"
    assert attempted[0] == "pkg/core.py:build"


def test_discriminator_probes_structural_recovery_target_first(monkeypatch, tmp_path):
    context = _context(tmp_path)
    context["failure_packet"]["retrieval_recovery_candidates"] = ["pkg/core.py:recover"]
    attempted = []

    def evaluate(_root, _project, **kwargs):
        attempted.append(kwargs["evaluation_target"])
        return {
            "status": "ok", "project_min_score": 9.7,
            "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.7},
            "selected_extraction_candidate": kwargs["evaluation_target"],
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        }

    monkeypatch.setattr("runtime.self_improvement_training._evaluate", evaluate)

    assert plugin.run(context)["status"] == "trial_passed"
    assert attempted[0] == "pkg/core.py:recover"

import json

from runtime.improvement_plugins.candidate_selection_evidence import (
    attach_ordinary_challenger_evidence,
)


def test_shadow_quality_uses_ordinary_challenger_ranking(tmp_path):
    spec = tmp_path / "TechnicalSpec.json"
    spec.write_text(json.dumps({"source_evidence": [{
        "source": "app.py:parse",
        "signature": {"args": [{"name": "value"}]},
        "snippet": "def parse(value):\n    return helper(value)\n",
        "unresolved_calls": ["helper"],
        "target_binding": "method_symbol",
        "dependency_readiness": {"status": "ready"},
    }]}), encoding="utf-8")
    control = {"artifacts": {"technical_spec": {"path": str(spec)}}}
    treatment = {"selected_candidate_quality": {"selection_evidence": {
        "ranking_reasons": ["clamped target"],
    }}}

    enriched = attach_ordinary_challenger_evidence(control, treatment, "app.py:parse")

    selection = enriched["selected_candidate_quality"]["selection_evidence"]
    assert selection["evidence_route"] == "ordinary_full_candidate_ranking"
    assert selection["ranking_reasons"] != ["clamped target"]
    assert selection["dependency_readiness"]["status"] == "ready"


def test_shadow_quality_recovers_dependency_evidence_for_unranked_target(tmp_path):
    (tmp_path / "app.py").write_text(
        "def normalize(value):\n    return value.strip()\n", encoding="utf-8",
    )
    treatment = {"selected_candidate_quality": {"selection_evidence": {}}}

    enriched = attach_ordinary_challenger_evidence(
        {}, treatment, "app.py:normalize", project_dir=tmp_path,
    )

    selection = enriched["selected_candidate_quality"]["selection_evidence"]
    assert selection["dependency_readiness"]["status"] == "ready"
    assert selection["evidence_route"] == "static_target_dependency_analysis"


def test_unranked_shadow_uses_same_viability_rules_as_architect(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Service:\n    def normalize(self, value):\n        return value.strip()\n",
        encoding="utf-8",
    )
    enriched = attach_ordinary_challenger_evidence(
        {}, {"selected_candidate_quality": {"selection_evidence": {}}},
        "app.py:Service.normalize", project_dir=tmp_path,
    )

    reasons = enriched["selected_candidate_quality"]["selection_evidence"]["ranking_reasons"]
    assert any("bounded_transform_boundary" in reason for reason in reasons)

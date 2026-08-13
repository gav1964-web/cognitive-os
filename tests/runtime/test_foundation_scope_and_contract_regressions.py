from runtime._parts.role_foundation_field_trial_scope import _primary_language_scope
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.technical_spec_policy import load_technical_spec_policy


def test_scope_rejects_independent_project_collection(tmp_path):
    for index in range(10):
        member = tmp_path / "Projects" / f"{index}_demo"
        member.mkdir(parents=True)
        (member / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_ignores_example_fixture_when_root_cli_is_product(tmp_path):
    (tmp_path / "scenarios" / "example_fixture").mkdir(parents=True)
    (tmp_path / "scenarios" / "example_fixture" / "verify.py").write_text("def run():\n    return 1\n")
    (tmp_path / "product.py").write_text("def deploy():\n    return True\n")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "in_scope"


def test_metric_and_model_query_contract_families_are_profiled():
    assert contract_archetype_for_target("dns/_ddr.py:ddr_tls_check_async")["contract_archetype"] == (
        "async_tls_validation_boundary"
    )
    assert contract_archetype_for_target("sketch/metrics.py:binary_metrics")["contract_archetype"] == (
        "metric_comparison_transform"
    )
    assert contract_archetype_for_target("purchase/model.py:query")["contract_archetype"] == "model_query_boundary"
    assert contract_archetype_for_target("httpcore/_async/http2.py:handle_async_request") == {}


def test_process_boundary_override_does_not_allow_known_too_broad_profile():
    override = load_technical_spec_policy()["process_boundary_review_override"]

    assert override["enabled"] is False
    assert "legacy_batch_orchestrator_too_broad" not in override["required_profile_ids"]

from runtime.contract_archetype_inference import contract_archetype_for_target


def test_contract_archetypes_cover_cli_identity_and_ml_boundaries():
    cases = {
        "sherlock_project/sherlock.py:sherlock": "identity_discovery_query_boundary",
        "supervised_learning/knn.py:predict": "model_inference_transform_boundary",
        "ml/estimators/regressor.py:fit": "model_training_boundary",
    }

    for target, expected in cases.items():
        contract = contract_archetype_for_target(target)
        assert contract["contract_archetype"] == expected
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]


def test_cli_and_ml_archetypes_require_domain_paths():
    for target in ("http/client.py:predict", "runtime/state.py:fit"):
        assert contract_archetype_for_target(target) == {}

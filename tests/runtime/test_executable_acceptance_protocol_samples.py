from pathlib import Path

from runtime.executable_acceptance_contract_inference import infer_argument_samples


def test_infers_safe_methods_called_on_protocol_parameter(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "def filter_values(source):\n    return (item for item in source.get_values())\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "filter_values") == {
        "source": {
            "value": {
                "__fixture__": "declared_model",
                "type": "AcceptanceProtocol",
                "fields": {"get_values": {"__fixture__": "callable_empty_list"}},
            },
            "source": "ast_parameter_methods",
        }
    }


def test_iterated_literal_domain_produces_nonempty_collection(tmp_path: Path):
    path = tmp_path / "features.py"
    path.write_text(
        "def extract(values, feature_list):\n"
        "    for feature in feature_list:\n"
        "        if feature == 'mean':\n"
        "            return values\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "extract")["feature_list"] == {
        "value": ["mean"],
        "source": "ast_iterated_literal_domain",
    }

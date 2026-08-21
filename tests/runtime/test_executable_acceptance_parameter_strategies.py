from pathlib import Path

from runtime.executable_acceptance_contract_inference import infer_argument_samples
from runtime.executable_acceptance_policy import (
    load_executable_acceptance_policy,
    temporary_executable_acceptance_policy,
)


def _infer(tmp_path: Path, source: str, strategy: str):
    path = tmp_path / "module.py"
    path.write_text(source, encoding="utf-8")
    policy = load_executable_acceptance_policy()
    policy["structural_sample_policy"]["parameter_strategies"][strategy] = True
    with temporary_executable_acceptance_policy(policy):
        return infer_argument_samples(path, "target")


def test_nested_mapping_strategy_preserves_required_path(tmp_path: Path):
    result = _infer(
        tmp_path,
        "def target(config):\n"
        "    for label in config['labels']:\n"
        "        return label['name']\n",
        "nested_mapping_paths",
    )

    assert result["config"] == {
        "value": {"labels": [{"name": "sample"}]},
        "source": "ast_strategy:iterated_mapping_paths",
    }


def test_callable_arity_strategy_uses_zero_argument_fixture(tmp_path: Path):
    result = _infer(
        tmp_path,
        "def target(model_class):\n    return model_class()\n",
        "callable_arity",
    )

    assert result["model_class"] == {
        "value": {"__fixture__": "callable_noop"},
        "source": "ast_strategy:callable_arity:0",
    }


def test_nested_mapping_strategy_propagates_tabular_columns(tmp_path: Path):
    result = _infer(
        tmp_path,
        "def target(config):\n"
        "    rows = pd.DataFrame(config['labels'])\n"
        "    return rows['name']\n",
        "nested_mapping_paths",
    )

    assert result["config"] == {
        "value": {"labels": [{"name": "sample"}]},
        "source": "ast_strategy:tabular_mapping_paths",
    }


def test_derived_conversion_strategy_tracks_transformed_parameter(tmp_path: Path):
    result = _infer(
        tmp_path,
        "def target(value):\n"
        "    parts = value.split(',')\n"
        "    for part in parts:\n"
        "        start, _, end = part.partition('-')\n"
        "        return int(start)\n",
        "derived_conversion",
    )

    assert result["value"] == {
        "value": "1",
        "source": "ast_strategy:derived_conversion:int",
    }


def test_indexed_sequence_strategy_infers_required_length(tmp_path: Path):
    result = _infer(
        tmp_path,
        "def target(grid, mark):\n    return grid[0] == grid[8] == mark\n",
        "indexed_sequence",
    )

    assert result["grid"] == {
        "value": [0] * 9,
        "source": "ast_strategy:indexed_sequence",
    }

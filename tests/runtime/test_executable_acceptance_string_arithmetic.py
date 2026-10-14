from pathlib import Path

from runtime.executable_acceptance_contract_inference import infer_argument_samples


def test_string_sequence_concatenation_does_not_infer_numeric_sample(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "def indented_lines(prefix, string, plain_prefix=None):\n"
        "    lines = str(string).splitlines() or ['']\n"
        "    return [prefix + lines[0]] + [\n"
        "        ' ' * len(plain_prefix or prefix) + line for line in lines[1:]\n"
        "    ]\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "indented_lines") == {
        "plain_prefix": {"value": None, "source": "ast_declared_default"},
    }

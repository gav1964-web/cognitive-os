from pathlib import Path

from runtime.executable_acceptance_contract_inference import infer_argument_samples


def test_nested_datetime_qualified_call_uses_epoch_sample(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "import datetime\n"
        "def format_timestamp(timestamp):\n"
        "    value = datetime.datetime.utcfromtimestamp(timestamp)\n"
        "    return value.strftime('%Y-%m-%d')\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "format_timestamp") == {
        "timestamp": {
            "value": 0,
            "source": "ast_qualified_call:datetime.datetime.utcfromtimestamp",
        }
    }

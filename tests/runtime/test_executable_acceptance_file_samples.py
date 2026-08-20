from runtime.executable_acceptance_contract_inference import infer_argument_samples


def test_infers_delimited_file_from_open_split_unpack(tmp_path):
    path = tmp_path / "loader.py"
    path.write_text(
        "def load(path):\n"
        "    with open(path) as stream:\n"
        "        name, kind, value = next(stream).strip().split('\\t')\n"
        "    return name, kind, value\n",
        encoding="utf-8",
    )

    assert infer_argument_samples(path, "load")["path"] == {
        "value": {
            "__fixture__": "delimited_text_path",
            "delimiter": "\t",
            "columns": 3,
        },
        "source": "ast_delimited_text_path",
    }

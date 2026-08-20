from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_contract_inference import infer_argument_samples
from runtime.executable_acceptance_materializers import materialize
from tests.runtime.test_executable_acceptance import _plan


def test_infers_bounded_bytes_from_startswith_literal(tmp_path):
    source = tmp_path / "parser.py"
    source.write_text(
        "def parse(data):\n"
        "    if not data.startswith(b'cfdp'):\n"
        "        raise ValueError\n"
        "    return data[4]\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "parse")["data"]
    sample = materialize(inferred["value"])

    assert inferred["source"] == "ast_literal_buffer:startswith"
    assert isinstance(sample, bytes)
    assert sample.startswith(b"cfdp")
    assert len(sample) == 32


def test_infers_string_suffix_without_fixture(tmp_path):
    source = tmp_path / "paths.py"
    source.write_text(
        "def is_config(path):\n    return path.endswith('.json')\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "is_config")["path"]

    assert inferred["source"] == "ast_literal_buffer:endswith"
    assert inferred["value"].endswith(".json")
    assert len(inferred["value"]) == 32


def test_bytes_predicate_contract_executes_with_inferred_override(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "parser.py").write_text(
        "def parse(data):\n"
        "    if not data.startswith(b'cfdp'):\n"
        "        raise ValueError\n"
        "    return data[4]\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("parser.py:parse", {"data": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]["parser.py:parse"]["data"]
    assert evidence["source"] == "ast_literal_buffer:startswith"


def test_exact_qualified_call_infers_numpy_fixture(tmp_path):
    source = tmp_path / "loader.py"
    source.write_text(
        "import torch\n\ndef load(features):\n    return torch.from_numpy(features)\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "load")["features"]
    sample = materialize(inferred["value"])

    assert inferred["source"] == "ast_qualified_call:torch.from_numpy"
    assert type(sample).__module__ == "numpy"
    assert sample.shape == (2,)

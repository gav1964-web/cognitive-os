import logging

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_contract_inference import infer_argument_samples
from runtime.executable_acceptance_materializers import materialize
from tests.runtime.test_executable_acceptance import _plan


def test_get_message_protocol_infers_real_log_record(tmp_path):
    source = tmp_path / "formatter.py"
    source.write_text(
        "def render(record):\n    return record.getMessage()\n",
        encoding="utf-8",
    )

    inferred = infer_argument_samples(source, "render")["record"]

    assert inferred["source"] == "ast_parameter_callable_protocol:getMessage"
    assert isinstance(materialize(inferred["value"]), logging.LogRecord)


def test_logging_formatter_executes_with_log_record_fixture(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "formatter.py").write_text(
        "import logging\n\n"
        "class PaddingFormatter(logging.Formatter):\n"
        "    def format(self, record):\n"
        "        record.levelname = record.levelname.ljust(8)\n"
        "        return super().format(record)\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("formatter.py:PaddingFormatter.format", {"record": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    evidence = result["summary"]["argument_sample_evidence"]
    assert evidence["formatter.py:PaddingFormatter.format"]["record"]["source"] == (
        "ast_inherited_method_contract:logging.Formatter.format"
    )

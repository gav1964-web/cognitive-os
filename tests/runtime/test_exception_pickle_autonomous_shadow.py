from __future__ import annotations

from tests.runtime.exception_pickle_autonomous_shadow_helpers import *

def test_autonomous_shadow_prepares_patch_without_counting_as_verified(
    tmp_path: Path,
):
    for index in range(3):
        _write_verified_report(tmp_path / f"report-{index}.json")
    holdout = tmp_path / "holdout"
    holdout.mkdir()
    (holdout / "pkg.py").write_text(
        "class HoldoutError(RuntimeError):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(f'value={value}')\n",
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "artifact_type": "SupervisedTransferLedger",
            "status": "threshold_met",
            "target_count": 3,
            "verified_count": 3,
            "autonomous_verified_count": 0,
            "cases": [
                {
                    "project": f"used-{index}",
                    "target": f"pkg.py:Used{index}.__init__",
                    "report": f"report-{index}.json",
                    "status": "verified_in_sandbox",
                }
                for index in range(3)
            ],
            "safety": {
                "source_apply": False,
                "kb_promotion": False,
                "untouched_holdout_used": False,
            },
        }),
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "scan": {"untouched_holdout_scanned": False},
            "candidates": [
                {
                    "canonical_project": f"holdout-{index}",
                    "project_root": "holdout",
                    "path": "pkg.py",
                    "class_name": "HoldoutError",
                    "score": 7 - index,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                }
                for index in range(3)
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_autonomous_shadow(
        root=tmp_path,
        execution_dir=tmp_path / "shadow",
        ledger_path=ledger,
        audit_path=audit,
    )

    assert report["status"] == "autonomous_verified_shadow"
    assert report["candidate"]["project"] == "holdout-0"
    assert report["sandbox_changed_python_files"] == ["pkg.py"]
    assert report["project_native_semantic_replay"]["status"] == "passed"
    assert report["counts_as_autonomous_verified_transformation"] is True
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False
    assert "def __reduce__" not in (holdout / "pkg.py").read_text(encoding="utf-8")


def test_autonomous_shadow_samples_safe_materializer_frontier():
    string_names = {
        "var_name",
        "got_type",
        "resource_type",
        "property_name",
        "ad_id",
        "txn_id",
        "table_name",
        "shared_lib_path",
        "error_type",
        "connection_id",
        "import_name",
        "func_name",
        "task_name",
        "guild_id",
        "service_name",
        "job_id",
        "stream_name",
        "auth_url",
        "file_path",
        "domain",
        "service",
    }
    for name in string_names:
        assert _sample_constructor_value(name) == f"sample-{name}"
    assert (
        _sample_constructor_value("agent_generator_build_step_filepath")
        == "sample-agent_generator_build_step_filepath.py"
    )
    assert _sample_constructor_value("number") == 7
    assert _sample_constructor_value("source_count") == 7
    assert _sample_constructor_value("failure_count") == 7
    assert _sample_constructor_value("values") == ["sample-values"]
    assert _sample_constructor_value("topics") == ["sample-topics"]
    assert _sample_constructor_value("bucket") == {
        "__sample__": "named_object",
        "name": "sample-bucket",
        "mention": "<sample-bucket>",
        "window": 7,
    }
    assert _sample_constructor_value("param")["displayed_name"] == "sample-param"
    assert _sample_constructor_value("flag")["max_args"] == 1
    assert _sample_constructor_value("flag")["annotation"] == "sample-annotation"
    assert (
        _sample_constructor_value("transformer")["_error_display_name"]
        == "sample-transformer"
    )
    assert _sample_constructor_value("parse_errors") == ["sample-parse_errors"]
    assert _sample_constructor_value("exception") == {
        "__sample__": "exception",
        "message": "sample-exception",
    }
    assert _sample_constructor_value("body") is None
    assert _sample_constructor_value(
        "domain",
        object_contracts={"domain": {"contract_kind": "string_like"}},
    ) == "sample-domain"
    assert _sample_constructor_value(
        "requirements",
        object_contracts={"requirements": {"contract_kind": "iterable_string_list"}},
    ) == ["sample-requirements"]
    assert _sample_constructor_value(
        "tarinfo",
        object_contracts={
            "tarinfo": {
                "contract_kind": "attribute_object",
                "evidence": {"attributes": ["name", "_private", "not valid"]},
            }
        },
    ) == {
        "__sample__": "named_object",
        "name": "sample-tarinfo",
        "mention": "<sample-tarinfo>",
    }
    assert _sample_constructor_value(
        "body",
        object_contracts={
            "body": {
                "contract_kind": "mapping_object",
                "evidence": {"mapping_keys": ["message", "status"]},
            }
        },
    ) == {"message": "sample-message", "status": "sample-status"}


def test_source_aware_sample_uses_string_for_sliced_line(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class SliceLineError(Exception):\n"
        "    def __init__(self, error_type, line):\n"
        "        self.error_type = error_type\n"
        "        self.line = line\n"
        "        super().__init__(f'{error_type}: {line[:100]}')\n\n"
        "class NumericLineNoError(Exception):\n"
        "    def __init__(self, lineno):\n"
        "        self.lineno = lineno\n"
        "        super().__init__(f'line {lineno}')\n",
        encoding="utf-8",
    )

    assert (
        _sample_constructor_value_for_source_file(
            "line",
            source_file=source,
            class_name="SliceLineError",
        )
        == "sample-line"
    )
    assert (
        _sample_constructor_value_for_source_file(
            "lineno",
            source_file=source,
            class_name="NumericLineNoError",
        )
        == 7
    )


def test_source_aware_sample_uses_called_process_error_for_process_attrs(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class GitCommandError(Exception):\n"
        "    def __init__(self, error):\n"
        "        self.error = error\n"
        "        super().__init__(error.stderr or error.stdout or error.returncode)\n",
        encoding="utf-8",
    )

    sample = _sample_constructor_value_for_source_file(
        "error",
        source_file=source,
        class_name="GitCommandError",
    )

    assert sample == {
        "__sample__": "called_process_error",
        "returncode": 7,
        "cmd": ["sample-command"],
        "stdout": "sample-stdout",
        "stderr": "sample-stderr",
    }


def test_source_aware_sample_uses_string_for_rendered_body(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class RestError(Exception):\n"
        "    def __init__(self, status_code, body):\n"
        "        self.status_code = status_code\n"
        "        self.body = body\n"
        "        super().__init__(f'response [{body}]')\n",
        encoding="utf-8",
    )

    assert _sample_constructor_value("body") is None
    assert (
        _sample_constructor_value_for_source_file(
            "body",
            source_file=source,
            class_name="RestError",
        )
        == "sample-body"
    )


def test_source_aware_sample_uses_string_membership_literal(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class ReplacementError(Exception):\n"
        "    def __init__(self, replacement_state):\n"
        "        if replacement_state not in {'installed', 'ambiguous'}:\n"
        "            raise ValueError(replacement_state)\n"
        "        self.replacement_state = replacement_state\n"
        "        super().__init__(replacement_state)\n",
        encoding="utf-8",
    )

    assert (
        _sample_constructor_value_for_source_file(
            "replacement_state",
            source_file=source,
            class_name="ReplacementError",
        )
        == "installed"
    )


def test_source_aware_sample_uses_string_for_lower_method_call(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class FailedStepError(Exception):\n"
        "    def __init__(self, failed_step):\n"
        "        self.failed_step = failed_step\n"
        "        super().__init__(failed_step.lower())\n",
        encoding="utf-8",
    )

    assert (
        _sample_constructor_value_for_source_file(
            "failed_step",
            source_file=source,
            class_name="FailedStepError",
        )
        == "sample-failed_step"
    )


def test_source_aware_sample_uses_named_object_for_attribute_name(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class LinkError(Exception):\n"
        "    def __init__(self, tarinfo, path):\n"
        "        self.tarinfo = tarinfo\n"
        "        self._path = path\n"
        "        super().__init__(f'{tarinfo.name!r} would link to {path!r}')\n",
        encoding="utf-8",
    )

    sample = _sample_constructor_value_for_source_file(
        "tarinfo",
        source_file=source,
        class_name="LinkError",
        object_contracts={},
    )

    assert sample == {
        "__sample__": "named_object",
        "name": "sample-tarinfo-name",
    }


def test_source_aware_sample_uses_named_object_for_content_and_tool_name(tmp_path: Path):
    source = tmp_path / "errors.py"
    source.write_text(
        "class ToolRetryError(Exception):\n"
        "    def __init__(self, tool_retry):\n"
        "        self.tool_retry = tool_retry\n"
        "        message = tool_retry.content if isinstance(tool_retry.content, str) else tool_retry.tool_name\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )

    sample = _sample_constructor_value_for_source_file(
        "tool_retry",
        source_file=source,
        class_name="ToolRetryError",
        object_contracts={},
    )

    assert sample == {
        "__sample__": "named_object",
        "content": "sample-tool_retry-content",
        "name": "sample-tool_retry",
        "tool_name": "sample-tool_retry-tool_name",
    }

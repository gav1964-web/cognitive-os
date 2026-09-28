from datetime import datetime, timezone
from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_materializers import materialize
from runtime.executable_acceptance_policy import sample_value


def _plan(target: str) -> dict[str, object]:
    return {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"result": "any"},
                    "oracle": "callable_executes",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": target,
                    "kind": "side_effect_scope_case",
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }


def test_datetime_annotation_uses_materializable_utc_fixture():
    configured = sample_value("datetime.datetime", "ts", signature_mode=True)

    assert configured == {"__fixture__": "datetime_utc"}
    assert materialize(configured) == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_log_record_annotation_uses_declared_object_fixture():
    configured = sample_value("logging.LogRecord", "record", signature_mode=True)

    assert configured["__fixture__"] == "declared_model"
    assert materialize(configured).__dict__ == {}


def test_acceptance_synthesizes_datetime_argument_from_annotation(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "clock.py").write_text(
        "import datetime\n"
        "def normalize_ts(ts: datetime.datetime) -> datetime.datetime:\n"
        "    return ts.replace(tzinfo=datetime.timezone.utc)\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("clock.py:normalize_ts"),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["clock.py:normalize_ts"] == {
        "ts": {"__fixture__": "datetime_utc"}
    }

from pathlib import Path

from runtime.patch_synthesis_policy import timestamp_range_error_contract_recipe
from runtime.programmer_patch_synthesizer import synthesize_patch_package
from runtime.programmer_timestamp_range_patch import timestamp_range_error_patch


SOURCE = '''import datetime as dt

def from_timestamp(value):
    try:
        return dt.datetime.fromtimestamp(value)
    except OverflowError as exc:
        raise ValueError("Timestamp is too large") from exc
    except OSError as exc:
        raise ValueError("Error converting value to datetime") from exc
'''


def test_timestamp_patch_normalizes_only_proven_range_handlers():
    result = timestamp_range_error_patch(
        SOURCE,
        symbol="from_timestamp",
        recipe=timestamp_range_error_contract_recipe(),
    )

    assert result is not None
    assert result["exceptions"] == ["OSError", "OverflowError"]
    assert result["source"].count("timestamp out of range") == 2


def test_timestamp_patch_rejects_incomplete_handler_shape():
    assert timestamp_range_error_patch(
        SOURCE.replace("except OSError as exc:", "except RuntimeError as exc:"),
        symbol="from_timestamp",
        recipe=timestamp_range_error_contract_recipe(),
    ) is None


def test_synthesizer_prepares_timestamp_range_patch(tmp_path: Path):
    project = tmp_path / "project"
    path = project / "src" / "demo" / "utils.py"
    path.parent.mkdir(parents=True)
    path.write_text(SOURCE, encoding="utf-8")
    plan = {
        "implementation_target": {"candidate": "src/demo/utils.py:from_timestamp"},
        "expected_files": ["src/demo/utils.py"],
        "writable_scope": ["src/demo/utils.py:from_timestamp"],
        "implementation_delta": {
            "status": "ready",
            "intent": {
                "operator_id": "normalize_timestamp_range_error",
                "allowed_operator_ids": ["normalize_timestamp_range_error"],
            },
        },
    }

    result = synthesize_patch_package(
        execution_dir=tmp_path / "execution",
        project_dir=project,
        implementation_plan=plan,
        test_plan={},
    )

    assert result["status"] == "prepared"
    assert result["patches"][0]["kind"] == "normalize_timestamp_range_error"

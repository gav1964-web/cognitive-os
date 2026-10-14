import json
from pathlib import Path

from runtime.exception_pickle_autonomous_shadow import (
    _sample_constructor_value,
    _sample_constructor_value_for_source_file,
    _target_import_stub_modules,
    run_exception_pickle_autonomous_shadow,
)


def _write_verified_report(path: Path) -> None:
    path.write_text(
        json.dumps({
            "implementation_result": {
                "status": "verified_in_sandbox",
                "semantic_verification": {"status": "passed"},
                "project_native_verification": {
                    "status": "passed",
                    "targeted_replay": {"status": "passed"},
                    "regression_suite": {"status": "passed"},
                },
                "stub_admission": {"status": "passed"},
                "source_invariant": {"unchanged": True},
                "source_apply": False,
                "memory_promotion": False,
            }
        }),
        encoding="utf-8",
    )

























__all__ = [name for name in globals() if not name.startswith("__")]

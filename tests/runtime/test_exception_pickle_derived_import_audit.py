import json
from pathlib import Path

from runtime.exception_pickle_derived_import_audit import (
    run_exception_pickle_derived_import_audit,
)


def test_derived_import_audit_splits_package_and_target_import_risk(tmp_path: Path):
    package_heavy = tmp_path / "package_heavy" / "pkg" / "sub"
    package_heavy.mkdir(parents=True)
    (package_heavy.parent / "__init__.py").write_text(
        "import heavy_a\nimport heavy_b\nimport heavy_c\n",
        encoding="utf-8",
    )
    (package_heavy / "errors.py").write_text(
        "class PackageHeavyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    target_heavy = tmp_path / "target_heavy"
    target_heavy.mkdir()
    (target_heavy / "errors.py").write_text(
        "import target_dep\n\n"
        "class TargetHeavyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    derived = tmp_path / "derived.json"
    derived.write_text(
        json.dumps({
            "cases": [
                _derived_case("package-heavy", "pkg/sub/errors.py:PackageHeavyError.__init__"),
                _derived_case("target-heavy", "errors.py:TargetHeavyError.__init__"),
            ]
        }),
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps({
            "candidates": [
                {
                    "canonical_project": "package-heavy",
                    "project_root": "package_heavy",
                    "path": "pkg/sub/errors.py",
                    "class_name": "PackageHeavyError",
                },
                {
                    "canonical_project": "target-heavy",
                    "project_root": "target_heavy",
                    "path": "errors.py",
                    "class_name": "TargetHeavyError",
                },
            ]
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_derived_import_audit(
        root=tmp_path,
        derived_message_audit_path=derived,
        candidate_audit_path=candidate,
    )

    assert report["case_count"] == 2
    assert report["lane_summary"] == {
        "derived_import_direct_file_fallback_candidate": 1,
        "derived_import_target_stub_candidate": 1,
    }
    assert report["recommended_next_lane"]["lane"] == "derived_import_direct_file_fallback_candidate"


def _derived_case(project: str, target: str) -> dict:
    return {
        "project": project,
        "target": target,
        "derived_message_lane": "derived_message_import_isolation_first",
        "required_input_signature": "message",
    }

from __future__ import annotations

from tests.runtime.exception_pickle_blocker_intelligence_helpers import *

def test_blocker_intelligence_counts_latest_blocker_per_target(tmp_path: Path):
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "errors.py").write_text(
        "class OutputError(Exception):\n"
        "    def __init__(self, output):\n"
        "        self.output = output\n"
        "        super().__init__(output)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "OutputError",
                "required_constructor_parameters": ["output"],
                "stored_constructor_parameters": ["output"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "blocked_cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:OutputError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:OutputError.__init__",
                    "blocker_kind": "semantic_replay_import_failed",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_blocker_intelligence(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["blocked_case_count"] == 1
    assert report["blocker_summary"] == {"semantic_replay_import_failed": 1}
    assert report["next_operator_lane_summary"] == {"import_dependency_isolation_candidate": 1}
    assert report["readmission_frontier_summary"]["case_count"] == 0

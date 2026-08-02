from __future__ import annotations

import json

from tools.field_trial_matrix import build_matrix


def test_field_trial_matrix_counts_patch_reasons_and_failed_checks(tmp_path):
    report = {
        "cases": [
            {
                "project": "a",
                "status": "ok",
                "quality_score": 1.0,
                "target_chain": {"implementation_target": "a.py:run"},
                "executor": {
                    "patch_synthesis_status": "prepared",
                    "patch_synthesis_reason": "required_input_guard_synthesized",
                    "acceptance_signal": "executable_callable",
                    "acceptance_skipped_reasons": {},
                    "callable_harness_count": 1,
                },
                "failed_checks": [],
            },
            {
                "project": "b",
                "status": "needs_review",
                "quality_score": 0.8,
                "target_chain": {"implementation_target": "b.py:run"},
                "executor": {
                    "patch_synthesis_status": "skipped",
                    "patch_synthesis_reason": "no_supported_patch_pattern",
                    "acceptance_signal": "meta_only",
                    "acceptance_skipped_reasons": {"import_failed": 1},
                    "acceptance_skipped_targets": [
                        {
                            "target": "b.py:run",
                            "reason": "import_failed",
                            "detail": "missing_lib: No module named 'missing_lib'",
                        }
                    ],
                    "callable_harness_count": 0,
                },
                "failed_checks": [{"code": "tester_covers_contract"}],
            },
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    matrix = build_matrix(path)

    assert matrix["summary"]["status_counts"] == {"needs_review": 1, "ok": 1}
    assert matrix["summary"]["acceptance_signals"] == {"executable_callable": 1, "meta_only": 1}
    assert matrix["summary"]["acceptance_skipped_reasons"] == {"import_failed": 1}
    assert matrix["summary"]["acceptance_skipped_details"] == {"missing_lib: No module named 'missing_lib'": 1}
    assert matrix["summary"]["patch_reasons"]["no_supported_patch_pattern"] == 1
    assert matrix["summary"]["failed_checks"] == {"tester_covers_contract": 1}

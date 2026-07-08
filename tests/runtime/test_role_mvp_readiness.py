from __future__ import annotations

from pathlib import Path

from tools.role_mvp_readiness import _programmer_executor_readiness


def test_programmer_executor_is_not_ready_without_patch_executor(tmp_path: Path):
    runs = {
        "impl_local": {"status": "ok", "summary": {"score": 1.0}},
        "impl_external": {"status": "ok", "summary": {"score": 1.0}},
        "impl_github": {
            "status": "ok",
            "project_count": 1,
            "summary": {
                "blocked_no_safe_candidate": 0,
                "writable_scope_targets_candidate": 1,
                "candidate_matches_spec": 1,
                "avg_quality_score": 1.0,
            },
        },
        "pipeline": {"summary": {"safety_score": 1.0}},
    }

    role = _programmer_executor_readiness(runs, tmp_path)

    assert role["role"] == "programmer_executor"
    assert role["mvp_ready"] is False
    assert "patch_executor_tool_exists" in role["remaining_work"]
    assert role["checks"]["implementation_plan_input_ready"] is True

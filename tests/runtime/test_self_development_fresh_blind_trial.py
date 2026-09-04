from __future__ import annotations

import copy
from pathlib import Path

from runtime.self_development_fresh_blind_trial import (
    load_fresh_blind_trial_policy,
    run_fresh_blind_trial,
)


ROOT = Path(__file__).resolve().parents[2]


def test_fresh_blind_batch_reaches_honest_evidence_exhaustion() -> None:
    report = run_fresh_blind_trial(root=ROOT, write=False)

    assert report["status"] == "evidence_exhausted"
    assert report["coverage"] == {
        "library_pure_transform": 3,
        "cli_local_tool": 3,
        "framework_plugin_build": 3,
    }
    assert report["summary"] == {
        "case_count": 10,
        "matched_count": 9,
        "contrast_count": 1,
        "recognized_count": 8,
        "systematic_issue_count": 2,
        "candidate_count": 0,
    }
    assert all(report["checks"].values())
    contrast = next(case for case in report["cases"] if case["contrast"])
    assert contrast["project"] == "lark-parser__lark"
    assert contrast["actual_project_type"] == "async_worker_scheduler"


def test_fresh_blind_trial_fails_when_one_target_type_loses_coverage() -> None:
    policy = copy.deepcopy(load_fresh_blind_trial_policy())
    for row in policy["sources"]:
        if row["expected_project_type"] == "cli_local_tool":
            row["expected_project_type"] = "library_pure_transform"

    report = run_fresh_blind_trial(root=ROOT, policy=policy, write=False)

    assert report["status"] == "needs_work"
    assert report["coverage"]["cli_local_tool"] == 0
    assert report["checks"]["target_type_coverage"] is False


def test_fresh_blind_policy_keeps_execution_read_only() -> None:
    policy = load_fresh_blind_trial_policy(
        str(ROOT / "config" / "self_development_fresh_blind_trial.json")
    )

    assert policy["invariants"]["chain_hint_used"] is False
    assert policy["invariants"]["sandbox_execution_used"] is False
    assert policy["invariants"]["promotion_applied"] is False

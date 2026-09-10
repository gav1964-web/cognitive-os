from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.self_development_shadow_trial import (
    SelfDevelopmentShadowTrialError,
    evaluate_shadow_dossier,
    load_self_development_shadow_trial_policy,
    run_self_development_shadow_trial,
)


ROOT = Path(__file__).resolve().parents[2]


def test_shadow_trial_policy_loads_real_mature_corpus() -> None:
    policy = load_self_development_shadow_trial_policy(
        str(ROOT / "config" / "self_development_shadow_trial.json")
    )

    assert len(policy["sources"]) == 3
    assert {row["expected_project_type"] for row in policy["sources"]} == {
        "library_pure_transform", "cli_local_tool", "framework_plugin_build",
    }
    assert policy["invariants"]["promotion_applied"] is False


def test_real_promotion_corpus_backfills_three_validated_l0_dossiers() -> None:
    report = run_self_development_shadow_trial(root=ROOT, write=False)

    assert report["status"] == "validated_shadow"
    assert report["summary"] == {
        "case_count": 3,
        "validated_case_count": 3,
        "minimum_score": 1.0,
        "change_classes": ["L0"],
        "project_types": [
            "cli_local_tool", "framework_plugin_build", "library_pure_transform",
        ],
    }
    assert all(report["checks"].values())
    assert all(case["source_unchanged"] for case in report["cases"])
    assert report["safety"]["source_apply"] is False
    assert report["safety"]["promotion_applied"] is False


def test_shadow_evaluator_rejects_wrong_expected_class() -> None:
    report = run_self_development_shadow_trial(root=ROOT, write=False)
    dossier = report["cases"][0]["dossier"]

    result = evaluate_shadow_dossier(
        dossier=dossier,
        expected_change_class="L3",
        expected_project_type="library_pure_transform",
        mature_project_types={"library_pure_transform"},
        minimum_score=0.9,
    )

    assert result["status"] == "needs_work"
    assert result["checks"]["classification_matches_expected"] is False


def test_shadow_evaluator_detects_tampered_impact_map() -> None:
    report = run_self_development_shadow_trial(root=ROOT, write=False)
    dossier = copy.deepcopy(report["cases"][0]["dossier"])
    dossier["proposal"]["impact_map"]["project_types"] = ["cli_local_tool"]

    result = evaluate_shadow_dossier(
        dossier=dossier,
        expected_change_class="L0",
        expected_project_type="library_pure_transform",
        mature_project_types={"library_pure_transform", "cli_local_tool"},
        minimum_score=0.9,
    )

    assert result["status"] == "needs_work"
    assert result["checks"]["impact_project_type_matches"] is False
    assert result["checks"]["proposal_integrity_passed"] is False


def test_shadow_trial_policy_rejects_unsafe_promotion_flag(tmp_path: Path) -> None:
    payload = json.loads(
        (ROOT / "config" / "self_development_shadow_trial.json").read_text(encoding="utf-8")
    )
    payload["invariants"]["promotion_applied"] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SelfDevelopmentShadowTrialError, match="invariants are unsafe"):
        load_self_development_shadow_trial_policy(str(path))


def test_shadow_trial_rejects_source_outside_workspace() -> None:
    policy = copy.deepcopy(load_self_development_shadow_trial_policy())
    policy["sources"][0]["path"] = "../outside.json"

    with pytest.raises(SelfDevelopmentShadowTrialError, match="escapes workspace"):
        run_self_development_shadow_trial(root=ROOT, policy=policy, write=False)

from __future__ import annotations

import json
from pathlib import Path

import pytest

import runtime.self_development_challenge_campaign as campaign


def _policy() -> dict:
    return {
        "schema_version": "self_development_challenge_campaign.v1",
        "status": "active",
        "corpus_index": "index.json",
        "certification_receipt": "receipt.json",
        "target_project_types": ["cli_local_tool", "library_pure_transform"],
        "acquisition_per_type": 2,
        "holdout_per_type": 2,
        "scan_limit": 20,
        "split_seed": "test",
        "prospective_evidence_glob": "artifacts/project_development/project_development_*.json",
        "signals": {
            "cli_local_tool": ["console_scripts", "argparse", "cli"],
            "library_pure_transform": ["parser", "transform", "schema"],
        },
        "required_name_signals": {
            "cli_local_tool": ["cli"],
            "library_pure_transform": ["pure"],
        },
        "excluded_signals": {
            "cli_local_tool": ["django"],
            "library_pure_transform": ["django"],
        },
        "external_acquisition": [],
        "invariants": {
            "untouched_only": True,
            "owner_independent": True,
            "content_independent": True,
            "holdout_frozen_before_execution": True,
            "external_acquisition_only_after_local_shortage": True,
            "holdout_consumed": False,
            "source_apply": False,
            "promotion_applied": False,
        },
    }


def _workspace(root: Path) -> None:
    projects = []
    for project_type, marker in (
        ("cli", "console_scripts argparse"),
        ("pure", "parser transform schema"),
    ):
        for index in range(5):
            name = f"owner-{project_type}-{index}__project"
            project = root / "corpus" / name
            project.mkdir(parents=True)
            (project / "README.md").write_text(marker, encoding="utf-8")
            (project / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            projects.append({
                "project": name,
                "canonical_project": name,
                "project_root": project.relative_to(root).as_posix(),
                "owner": f"owner-{project_type}-{index}",
                "content_fingerprint": f"{len(projects) + 1:064x}",
                "python_files_sampled": 2,
                "exposure": "untouched",
            })
    (root / "index.json").write_text(json.dumps({
        "status": "local_corpus_sufficient", "projects": projects,
        "acquisition": [], "holdout": [],
    }), encoding="utf-8")


def test_manifest_freezes_independent_local_splits(tmp_path: Path) -> None:
    _workspace(tmp_path)
    manifest = campaign.build_challenge_manifest(root=tmp_path, policy=_policy())

    assert manifest["status"] == "local_corpus_sufficient"
    assert manifest["network_fallback"]["allowed"] is False
    assert all(len(row["acquisition"]) == len(row["holdout"]) == 2 for row in manifest["splits"])
    assert all(all(row["checks"].values()) for row in manifest["splits"])


def test_policy_rejects_consumable_holdout(tmp_path: Path) -> None:
    policy = _policy()
    policy["invariants"]["holdout_consumed"] = True
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(campaign.ChallengeCampaignError, match="mutation boundary"):
        campaign.load_challenge_campaign_policy(str(path))


def test_cli_name_matching_is_token_aware() -> None:
    assert campaign._name_signal_matches("owner__my-cli-tool", "cli") is True
    assert campaign._name_signal_matches("owner__python-client", "cli") is False


def test_campaign_connects_reports_collector_detector_and_queue(tmp_path: Path, monkeypatch) -> None:
    _workspace(tmp_path)
    manifest = campaign.build_challenge_manifest(root=tmp_path, policy=_policy())
    monkeypatch.setattr(campaign, "run_project_development", lambda **kwargs: {
        "artifact_type": "ProjectDevelopmentRun",
        "status": "controlled_stop",
        "project": kwargs["project_dir"].name,
        "recognition": {"status": "recognized", "classification": {
            "project_stratum": "cli_local_tool" if "cli" in kwargs["project_dir"].name else "library_pure_transform"
        }},
        "diagnosis": {"issues": []},
        "safety": {"source_changes": False, "automatic_kb_promotion": False},
    })
    monkeypatch.setattr(campaign, "collect_project_development_report", lambda **kwargs: {"status": "collected"})
    monkeypatch.setattr(campaign, "run_prospective_detection", lambda **kwargs: {
        "status": "waiting_for_evidence", "candidate_count": 0, "report_path": "detector.json"
    })
    monkeypatch.setattr(campaign, "build_self_development_experiment_queue", lambda **kwargs: {
        "status": "waiting_for_candidate", "ready_count": 0
    })

    report = campaign.run_challenge_campaign(
        root=tmp_path, manifest=manifest, certification_receipt="receipt.json"
    )

    assert report["status"] == "completed"
    assert report["summary"]["executed"] == 4
    assert report["summary"]["expected_type_matches"] == 4
    assert len(report["manifest_snapshot"]["splits"]) == 2
    assert report["safety"]["holdout_consumed"] is False

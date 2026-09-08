from __future__ import annotations

import json
from pathlib import Path

import runtime.narrow_type_fresh_holdout as holdout


def _manifest(root: Path) -> dict:
    cases = []
    for stratum in holdout.REQUIRED_STRATA:
        for index in range(2):
            project = root / "projects" / f"{stratum}-{index}"
            (project / "tests").mkdir(parents=True)
            (project / ".git").mkdir()
            ordinal = len(cases) + 1
            cases.append({
                "project": project.name,
                "project_stratum": stratum,
                "source_owner": f"owner-{stratum}-{index}",
                "source_url": f"https://example.test/{project.name}.git",
                "revision": f"{ordinal:040x}",
                "project_root": project.relative_to(root).as_posix(),
                "content_digest": f"sha256:{ordinal:064x}",
                "native_test_roots": ["tests"],
            })
    source = {
        "manifest_digest": "sha256:source",
        "shortages": {stratum: {"holdout": 0} for stratum in holdout.REQUIRED_STRATA},
    }
    source_path = root / "source.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    return {
        "schema_version": "narrow_type_fresh_holdout.v1",
        "status": "frozen",
        "evaluation_split": "owner_independent_unseen_project_holdout",
        "source_challenge_manifest": "source.json",
        "source_challenge_manifest_digest": "sha256:source",
        "holdout_consumed": False,
        "cases": cases,
        "invariants": {
            "two_projects_per_stratum": True,
            "distinct_source_owners": True,
            "content_disjoint": True,
            "clean_git_worktrees": True,
            "exact_revisions_bound": True,
            "native_tests_present": True,
            "project_development_unexposed_at_freeze": True,
            "native_failure_unexposed_at_freeze": True,
            "holdout_frozen_before_execution": True,
            "source_apply": False,
            "knowledge_updates_before_evaluation": False,
            "automatic_promotion": False,
        },
    }


def _snapshots(manifest: dict) -> dict[str, dict[str, str]]:
    return {
        row["project"]: {
            "status": "",
            "revision": row["revision"],
            "origin": row["source_url"],
        }
        for row in manifest["cases"]
    }


def test_frozen_holdout_is_ready_when_all_evidence_is_bound(
    tmp_path: Path, monkeypatch,
) -> None:
    manifest = _manifest(tmp_path)
    snapshots = _snapshots(manifest)
    monkeypatch.setattr(
        holdout, "_git_snapshot", lambda path: snapshots[path.name]
    )

    report = holdout.validate_fresh_holdout_manifest(root=tmp_path, manifest=manifest)

    assert report["status"] == "ready"
    assert all(report["checks"].values())
    assert report["evidence_digest"].startswith("sha256:")


def test_holdout_blocks_revision_drift(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(tmp_path)
    snapshots = _snapshots(manifest)
    snapshots[manifest["cases"][0]["project"]]["revision"] = "f" * 40
    monkeypatch.setattr(
        holdout, "_git_snapshot", lambda path: snapshots[path.name]
    )

    report = holdout.validate_fresh_holdout_manifest(root=tmp_path, manifest=manifest)

    assert report["status"] == "blocked"
    assert report["checks"]["exact_revisions_bound"] is False


def test_holdout_blocks_project_development_exposure(
    tmp_path: Path, monkeypatch,
) -> None:
    manifest = _manifest(tmp_path)
    snapshots = _snapshots(manifest)
    monkeypatch.setattr(
        holdout, "_git_snapshot", lambda path: snapshots[path.name]
    )
    reports = tmp_path / "artifacts" / "project_development"
    reports.mkdir(parents=True)
    (reports / "project_development_seen.json").write_text(
        json.dumps({"project": manifest["cases"][0]["project"]}), encoding="utf-8"
    )

    report = holdout.validate_fresh_holdout_manifest(root=tmp_path, manifest=manifest)

    assert report["status"] == "blocked"
    assert report["checks"]["project_development_unexposed"] is False


def test_holdout_blocks_native_failure_intake_exposure(
    tmp_path: Path, monkeypatch,
) -> None:
    manifest = _manifest(tmp_path)
    snapshots = _snapshots(manifest)
    monkeypatch.setattr(
        holdout, "_git_snapshot", lambda path: snapshots[path.name]
    )
    reports = tmp_path / "artifacts" / "field_trials"
    reports.mkdir(parents=True)
    (reports / "project_native_failure_intake_seen.json").write_text(
        json.dumps({"cases": [{"project": manifest["cases"][0]["project"]}]}),
        encoding="utf-8",
    )

    report = holdout.validate_fresh_holdout_manifest(root=tmp_path, manifest=manifest)

    assert report["status"] == "blocked"
    assert report["checks"]["native_failure_unexposed"] is False

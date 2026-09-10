from __future__ import annotations

from pathlib import Path

import pytest

import runtime.local_history_acquisition as acquisition
from runtime.local_historical_defect_evidence import evidence_digest


def _manifest(root: Path) -> dict:
    suggestions = {}
    for project_type, owner in zip(acquisition.TARGET_TYPES, ("owner-a", "owner-b")):
        project = root / owner
        (project / ".git").mkdir(parents=True)
        suggestions[project_type] = [{
            "project": owner, "project_stratum": project_type, "owner": owner,
            "project_root": project.relative_to(root).as_posix(),
            "source_url": f"https://github.com/{owner}/project.git",
            "snapshot_revision": owner[-1] * 40,
        }]
    manifest = {
        "schema_version": "local_historical_defect_public_manifest.v1",
        "status": "shortage",
        "checks": {"selection": True, "minimum_candidates_met": False},
        "network_fallback": {"required": True, "suggested_sources": suggestions},
    }
    _seal(manifest)
    return manifest


def _seal(manifest: dict) -> None:
    manifest["manifest_digest"] = evidence_digest({
        key: value for key, value in manifest.items() if key != "manifest_digest"
    })


def test_acquisition_deepens_history_without_moving_head(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(tmp_path)
    depths = {"owner-a": 1, "owner-b": 1}

    def snapshot(project: Path) -> dict[str, str]:
        owner = project.name
        return {
            "status": "", "revision": owner[-1] * 40,
            "origin": f"https://github.com/{owner}/project.git",
            "shallow": "true", "history_count": str(depths[owner]),
        }

    def fetch(project: Path, args: list[str], timeout: int = 20) -> str:
        assert args[:2] == ["fetch", "--deepen=160"]
        assert timeout == 180
        depths[project.name] = 161
        return ""

    monkeypatch.setattr(acquisition, "_git_snapshot", snapshot)
    monkeypatch.setattr(acquisition, "_git", fetch)

    report = acquisition.acquire_local_history(
        root=tmp_path, manifest=manifest, deepen=160,
    )

    assert report["status"] == "completed"
    assert report["summary"] == {"selected": 2, "acquired": 2, "failed": 0}
    assert all(row["head_unchanged"] for row in report["results"])
    assert all(row["worktree_unchanged"] for row in report["results"])
    assert all(row["after_history_count"] == 161 for row in report["results"])


def test_acquisition_refuses_origin_mismatch(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(tmp_path)
    first = manifest["network_fallback"]["suggested_sources"][acquisition.TARGET_TYPES[0]][0]
    first["source_url"] = "https://gitlab.com/owner-a/project.git"
    _seal(manifest)
    calls = []

    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: {
        "status": "", "revision": project.name[-1] * 40,
        "origin": f"https://github.com/{project.name}/project.git",
        "shallow": "true", "history_count": "1",
    })
    monkeypatch.setattr(
        acquisition, "_git", lambda project, args, timeout=20: calls.append(project.name) or "",
    )

    report = acquisition.acquire_local_history(root=tmp_path, manifest=manifest)

    assert report["status"] == "blocked"
    assert report["results"][0]["reason"] == "acquisition_admission_failed"
    assert calls == ["owner-b"]


def test_acquisition_rejects_fix_oracle_disclosure(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    first = manifest["network_fallback"]["suggested_sources"][acquisition.TARGET_TYPES[0]][0]
    first["fix_revision"] = "f" * 40
    _seal(manifest)

    with pytest.raises(acquisition.LocalHistoryAcquisitionError):
        acquisition.acquire_local_history(root=tmp_path, manifest=manifest)


def test_acquisition_can_target_only_missing_project_type(
    tmp_path: Path, monkeypatch,
) -> None:
    manifest = _manifest(tmp_path)
    project_type = "library_pure_transform"
    depths = {"owner-b": 1}
    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: {
        "status": "", "revision": "b" * 40,
        "origin": "https://github.com/owner-b/project.git",
        "shallow": "true", "history_count": str(depths[project.name]),
    })

    def fetch(project: Path, args: list[str], timeout: int = 20) -> str:
        depths[project.name] = 20
        return ""

    monkeypatch.setattr(acquisition, "_git", fetch)

    report = acquisition.acquire_local_history(
        root=tmp_path, manifest=manifest, project_types=(project_type,),
    )

    assert report["status"] == "completed"
    assert report["request"]["project_types"] == [project_type]
    assert [row["project"] for row in report["results"]] == ["owner-b"]


def test_acquisition_rejects_manifest_drift_before_git(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(tmp_path)
    first = manifest["network_fallback"]["suggested_sources"][acquisition.TARGET_TYPES[0]][0]
    first["snapshot_revision"] = "c" * 40
    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: pytest.fail("read Git"))

    with pytest.raises(acquisition.LocalHistoryAcquisitionError, match="manifest digest mismatch"):
        acquisition.acquire_local_history(root=tmp_path, manifest=manifest)


@pytest.mark.parametrize("mutation", ["owner", "project", "origin", "stratum", "types"])
def test_acquisition_checks_selection_before_git(
    tmp_path: Path, monkeypatch, mutation: str,
) -> None:
    manifest = _manifest(tmp_path)
    suggestions = manifest["network_fallback"]["suggested_sources"]
    first = suggestions[acquisition.TARGET_TYPES[0]][0]
    selected_types = None
    if mutation == "owner":
        suggestions[acquisition.TARGET_TYPES[0]].append({**first, "project_root": "another"})
    elif mutation == "project":
        suggestions[acquisition.TARGET_TYPES[1]][0]["project_root"] = first["project_root"] + "/."
    elif mutation == "origin":
        first["source_url"] = "https://example.test/project.git"
    elif mutation == "stratum":
        first["project_stratum"] = acquisition.TARGET_TYPES[1]
    else:
        selected_types = (acquisition.TARGET_TYPES[0],) * 2
    _seal(manifest)
    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: pytest.fail("read Git"))

    with pytest.raises(acquisition.LocalHistoryAcquisitionError):
        acquisition.acquire_local_history(root=tmp_path, manifest=manifest, project_types=selected_types)


@pytest.mark.parametrize("after", [
    {"status": "", "revision": "c" * 40, "history_count": "1"},
    {"status": " M source.py", "revision": "a" * 40, "history_count": "1"},
    {},
])
def test_failed_fetch_measures_source_invariants(tmp_path: Path, monkeypatch, after: dict) -> None:
    manifest = _manifest(tmp_path)
    before = {
        "status": "", "revision": "a" * 40,
        "origin": "https://github.com/owner-a/project.git", "history_count": "1",
    }
    snapshots = iter((before, after))
    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: next(snapshots))

    def fail_fetch(*args, **kwargs):
        raise acquisition.HistoricalDefectMiningError("fetch failed")

    monkeypatch.setattr(acquisition, "_git", fail_fetch)
    report = acquisition.acquire_local_history(
        root=tmp_path, manifest=manifest, project_types=(acquisition.TARGET_TYPES[0],),
    )

    result = report["results"][0]
    assert result["reason"] == "git_fetch_failed"
    assert result["head_unchanged"] is (after.get("revision") == before["revision"])
    assert result["worktree_unchanged"] is (after.get("status") == "")
    assert not all(report["checks"].values())


@pytest.mark.parametrize("checks", [{}, {"source_index_sufficient": False}])
def test_acquisition_rejects_failed_selection_checks(tmp_path: Path, monkeypatch, checks: dict) -> None:
    manifest = _manifest(tmp_path)
    manifest["checks"] = checks
    _seal(manifest)
    monkeypatch.setattr(acquisition, "_git_snapshot", lambda project: pytest.fail("read Git"))

    with pytest.raises(acquisition.LocalHistoryAcquisitionError, match="selection checks failed"):
        acquisition.acquire_local_history(root=tmp_path, manifest=manifest)

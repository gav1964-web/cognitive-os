from __future__ import annotations

import json
from pathlib import Path

import pytest

import runtime.local_historical_defect_mining as mining


def _policy() -> dict:
    return {
        "schema_version": mining.SCHEMA_VERSION,
        "status": "active",
        "corpus_index": "index.json",
        "target_project_types": list(mining.TARGET_TYPES),
        "minimum_candidates_per_type": 1,
        "scan_limit": 10,
        "max_commits_per_project": 20,
        "max_changed_files": 5,
        "max_production_python_files": 2,
        "max_test_python_files": 2,
        "split_seed": "test",
        "fix_message_tokens": ["fix", "bug"],
        "prospective_evidence_glob": "artifacts/project_development/*.json",
        "native_failure_evidence_glob": "artifacts/field_trials/*.json",
        "historical_selection_evidence_glob": "artifacts/history/*.json",
        "signals": {
            "cli_local_tool": ["cli"],
            "library_pure_transform": ["parser", "schema"],
        },
        "required_library_name_signals": ["parser", "schema"],
        "excluded_cli_signals": ["fastapi"],
        "excluded_library_signals": ["django"],
        "invariants": {
            "local_corpus_first": True,
            "untouched_projects_only": True,
            "owner_independent": True,
            "production_and_test_delta_required": True,
            "baseline_frozen_before_execution": True,
            "fix_oracle_separated": True,
            "source_apply": False,
            "automatic_promotion": False,
        },
    }


def _workspace(root: Path) -> list[Path]:
    projects = []
    rows = []
    for name, owner in (("owner-a__cli", "owner-a"), ("owner-b__parser", "owner-b")):
        project = root / "projects" / name
        (project / ".git").mkdir(parents=True)
        (project / "tests").mkdir()
        (project / "pyproject.toml").write_text(
            "[project]\nname='demo'\n" + (
                "[project.scripts]\ndemo='demo:main'\n" if name.endswith("cli") else ""
            ), encoding="utf-8",
        )
        if name.endswith("parser"):
            (project / "README.md").write_text("parser schema", encoding="utf-8")
        projects.append(project)
        rows.append({
            "project": name, "canonical_project": name, "owner": owner,
            "project_root": project.relative_to(root).as_posix(),
            "content_fingerprint": f"fingerprint-{owner}", "exposure": "untouched",
        })
    (root / "index.json").write_text(json.dumps({
        "schema_version": "self_development_corpus_eligibility_index.v1",
        "status": "local_corpus_sufficient", "projects": rows,
        "acquisition": [], "holdout": [],
    }), encoding="utf-8")
    return projects


def test_miner_separates_public_baseline_from_fix_oracle(tmp_path: Path, monkeypatch) -> None:
    projects = _workspace(tmp_path)

    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "false", "history_count": "2",
    })
    monkeypatch.setattr(mining, "_git", lambda project, args, timeout=20: (
        f"{'2' * 40}\x1f{'1' * 40}\x1ffix parser bug\n" if args[0] == "log" else
        "M\tsrc/core.py\nA\ttests/test_core.py\nA\ttests/data/case.json\n"
        if args[0] == "diff-tree" else
        "bounded patch"
    ))

    result = mining.mine_historical_defect_candidates(
        root=tmp_path, policy=_policy(), write=True,
    )

    public = result["public_manifest"]
    oracle = result["oracle_manifest"]
    assert public["status"] == "ready"
    assert len(public["cases"]) == len(projects)
    assert all("fix_revision" not in row for row in public["cases"])
    assert {row["oracle_ref"] for row in public["cases"]} == {
        row["candidate_id"] for row in oracle["cases"]
    }
    assert all("tests/data/case.json" in row["test_files"] for row in oracle["cases"])
    assert result["paths"]["public"] != result["paths"]["oracle"]


def test_miner_rejects_test_only_fix(tmp_path: Path, monkeypatch) -> None:
    _workspace(tmp_path)
    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "false", "history_count": "2",
    })
    monkeypatch.setattr(mining, "_git", lambda project, args, timeout=20: (
        f"{'2' * 40}\x1f{'1' * 40}\x1ffix bug\n" if args[0] == "log" else
        "A\ttests/test_core.py\n" if args[0] == "diff-tree" else ""
    ))

    result = mining.mine_historical_defect_candidates(
        root=tmp_path, policy=_policy(),
    )

    assert result["public_manifest"]["status"] == "shortage"
    assert result["public_manifest"]["cases"] == []


def test_miner_excludes_dynamically_exposed_project(tmp_path: Path, monkeypatch) -> None:
    projects = _workspace(tmp_path)
    evidence = tmp_path / "artifacts" / "project_development"
    evidence.mkdir(parents=True)
    (evidence / "seen.json").write_text(
        json.dumps({"project": projects[0].name}), encoding="utf-8"
    )
    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "false", "history_count": "2",
    })
    monkeypatch.setattr(mining, "_git", lambda project, args, timeout=20: (
        f"{'2' * 40}\x1f{'1' * 40}\x1ffix bug\n" if args[0] == "log" else
        "M\tsrc/core.py\nA\ttests/test_core.py\n" if args[0] == "diff-tree" else
        "patch"
    ))

    result = mining.mine_historical_defect_candidates(root=tmp_path, policy=_policy())

    assert {row["project"] for row in result["public_manifest"]["cases"]} == {
        projects[1].name
    }


def test_miner_justifies_history_download_for_shallow_snapshots(
    tmp_path: Path, monkeypatch,
) -> None:
    projects = _workspace(tmp_path)
    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "true", "history_count": "1",
    })

    result = mining.mine_historical_defect_candidates(root=tmp_path, policy=_policy())

    public = result["public_manifest"]
    suggestions = public["network_fallback"]["suggested_sources"]
    assert public["status"] == "shortage"
    assert public["network_fallback"]["required"] is True
    assert sum(len(rows) for rows in suggestions.values()) == len(projects)
    assert public["summary"]["history_capable_git_repositories"] == 0


def test_classifier_rejects_broad_framework_with_cli_script(tmp_path: Path) -> None:
    project = tmp_path / "framework-cli"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname='framework'\n[project.scripts]\napp='app:main'\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("FastAPI service", encoding="utf-8")

    assert mining._classify(project, _policy()) == ("", "unqualified_project_type")


@pytest.mark.parametrize("description,admitted", [
    ("Parser schema library. See the user guide and contributing guidelines.", True),
    ("Parser schema library with a GUI.", False),
    ("Parser schema library for Django applications.", False),
])
def test_classifier_distinguishes_gui_from_guide(tmp_path: Path, description, admitted) -> None:
    project = _workspace(tmp_path)[1]
    (project / "README.md").write_text(description, encoding="utf-8")
    policy = _policy()
    policy["excluded_library_signals"] = ["gui", "django"]

    assert (mining._classify(project, policy)[0] == "library_pure_transform") is admitted


def test_library_only_scan_does_not_reserve_cli_candidates(tmp_path: Path, monkeypatch) -> None:
    projects = _workspace(tmp_path)
    monkeypatch.setattr(mining, "_git_snapshot", lambda project: {
        "status": "", "revision": "f" * 40,
        "origin": f"https://example.test/{project.name}.git",
        "shallow": "true", "history_count": "1",
    })
    public = mining.mine_historical_defect_candidates(
        root=tmp_path, policy=_policy(), project_types=("library_pure_transform",),
    )["public_manifest"]

    assert public["network_fallback"]["suggested_sources"]["cli_local_tool"] == []
    assert [r["project"] for r in public["network_fallback"]["suggested_sources"]["library_pure_transform"]] == [projects[1].name]
    assert public["summary"]["rejection_counts"]["project_type_not_requested"] == 1
    assert public["request"] == {"project_types": ["library_pure_transform"], "scan_limit": 10}
    assert public["status"] == "shortage"


@pytest.mark.parametrize("project_types", [(), ("unknown",), ("cli_local_tool", "cli_local_tool")])
def test_mining_rejects_invalid_scope_before_reading_corpus(tmp_path: Path, project_types) -> None:
    with pytest.raises(mining.HistoricalDefectMiningError, match="project types"):
        mining.mine_historical_defect_candidates(root=tmp_path, project_types=project_types)


def test_classifier_allows_empty_exclusions(tmp_path: Path) -> None:
    projects = _workspace(tmp_path)
    policy = _policy()
    policy["excluded_cli_signals"] = []
    policy["excluded_library_signals"] = []

    assert [mining._classify(project, policy)[0] for project in projects] == list(mining.TARGET_TYPES)

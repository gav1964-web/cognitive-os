from __future__ import annotations

import json
from pathlib import Path

from runtime.framework_plugin_holdout_selection import (
    build_framework_plugin_holdout_selection,
)


def _project(root: Path, name: str, manifest: str, source: str = "") -> dict:
    project = root / name
    project.mkdir()
    (project / "pyproject.toml").write_text(manifest, encoding="utf-8")
    (project / "plugin.py").write_text(source or "VALUE = 1\n", encoding="utf-8")
    return {
        "project": name,
        "canonical_project": name.lower(),
        "owner": name.split("__", 1)[0].lower(),
        "project_root": name,
        "content_fingerprint": name,
        "exposure": "untouched",
    }


def _policy() -> dict:
    return {
        "schema_version": "framework_plugin_holdout_selection.v1",
        "status": "active",
        "minimum_acquisition_projects": 1,
        "minimum_holdout_projects": 1,
        "split_seed": "test",
        "plugin_entrypoint_groups": ["pytest11"],
        "owned_backend_required_functions": [
            "build_wheel", "build_sdist", "prepare_metadata_for_build_wheel"
        ],
        "skip_directories": ["venv", "site-packages"],
        "invariants": {
            "untouched_only": True,
            "root_manifest_authority": True,
            "project_owned_source_required": True,
            "owner_independence": True,
            "content_independence": True,
            "network_fallback_only_on_shortage": True,
            "source_apply": False,
            "promotion_applied": False,
        },
    }


def test_selects_declared_plugin_and_owned_backend(tmp_path: Path) -> None:
    plugin = _project(
        tmp_path,
        "alpha__plugin",
        '[project]\nname="plugin"\n[project.entry-points.pytest11]\na="plugin:hook"\n',
    )
    backend = _project(
        tmp_path,
        "beta__backend",
        '[project]\nname="backend"\n[build-system]\nbuild-backend="plugin"\n',
        "def build_wheel(): pass\ndef build_sdist(): pass\n"
        "def prepare_metadata_for_build_wheel(): pass\n",
    )
    eligibility = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "failed_checks": [],
        "generated_at": "now",
        "projects": [plugin, backend],
    }

    report = build_framework_plugin_holdout_selection(
        root=tmp_path, eligibility=eligibility, policy=_policy()
    )

    assert report["status"] == "local_corpus_sufficient"
    assert report["qualified_project_count"] == 2
    assert report["checks"]["all_selected_have_owned_contract"] is True
    assert report["failed_checks"] == []


def test_external_backend_usage_and_venv_source_do_not_qualify(tmp_path: Path) -> None:
    consumer = _project(
        tmp_path,
        "consumer__package",
        '[build-system]\nrequires=["setuptools"]\nbuild-backend="setuptools.build_meta"\n',
    )
    venv = tmp_path / "consumer__package" / "venv" / "site-packages"
    venv.mkdir(parents=True)
    (venv / "build_meta.py").write_text(
        "def build_wheel(): pass\ndef build_sdist(): pass\n"
        "def prepare_metadata_for_build_wheel(): pass\n",
        encoding="utf-8",
    )
    eligibility = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "failed_checks": [],
        "projects": [consumer],
    }

    report = build_framework_plugin_holdout_selection(
        root=tmp_path, eligibility=eligibility, policy=_policy()
    )

    assert report["status"] == "local_corpus_shortage"
    assert report["qualified_project_count"] == 0
    assert report["network_fallback"]["required"] is True


def test_declared_entrypoint_must_resolve_to_project_owned_source(tmp_path: Path) -> None:
    consumer = _project(
        tmp_path,
        "consumer__plugin",
        '[project]\nname="consumer"\n'
        '[project.entry-points.pytest11]\na="external_package:hook"\n',
    )
    eligibility = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "failed_checks": [],
        "projects": [consumer],
    }

    report = build_framework_plugin_holdout_selection(
        root=tmp_path, eligibility=eligibility, policy=_policy()
    )

    assert report["qualified_project_count"] == 0


def test_exposed_project_is_never_selected(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        "used__plugin",
        '[project]\nname="plugin"\n[project.entry-points.pytest11]\na="plugin:hook"\n',
    )
    project["exposure"] = "prospective_used"
    eligibility = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "failed_checks": [],
        "projects": [project],
    }

    report = build_framework_plugin_holdout_selection(
        root=tmp_path, eligibility=eligibility, policy=_policy()
    )

    assert report["qualified_project_count"] == 0
    assert report["holdout"] == []


def test_revision_bound_external_candidate_fills_measured_shortage(tmp_path: Path) -> None:
    local = _project(
        tmp_path,
        "alpha__plugin",
        '[project]\nname="plugin"\n[project.entry-points.pytest11]\na="plugin:hook"\n',
    )
    external = _project(
        tmp_path,
        "beta__external",
        '[project]\nname="external"\n[project.entry-points.pytest11]\nb="plugin:hook"\n',
    )
    git = tmp_path / "beta__external" / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
    (git / "refs" / "heads" / "main").write_text("abc123\n", encoding="ascii")
    candidate = {
        **external,
        "url": "https://github.com/beta/external",
        "revision": "abc123",
    }
    eligibility = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "failed_checks": [],
        "projects": [local],
    }

    report = build_framework_plugin_holdout_selection(
        root=tmp_path,
        eligibility=eligibility,
        external_candidates=[candidate],
        policy=_policy(),
    )

    assert report["status"] == "local_corpus_sufficient"
    assert report["qualified_external_project_count"] == 1
    assert report["checks"]["external_revisions_verified"] is True

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from runtime.self_development_corpus_eligibility import (
    CorpusEligibilityError,
    build_corpus_eligibility_index,
    load_corpus_eligibility_policy,
)


def _policy() -> dict:
    return {
        "schema_version": "self_development_corpus_eligibility.v1",
        "status": "active",
        "corpus_root": "artifacts",
        "source_directory_name": "src",
        "corpus_path_markers": ["github"],
        "prospective_evidence_glob": "artifacts/project_development/*.json",
        "historical_evidence_glob": "artifacts/field_trials/*.json",
        "target_markers": ["build-system", "wheel"],
        "identity_files": ["pyproject.toml", "README.md"],
        "minimum_python_files": 2,
        "minimum_acquisition_projects": 2,
        "minimum_holdout_projects": 2,
        "split_seed": "test",
        "invariants": {
            "untouched_only": True,
            "owner_independence": True,
            "content_independence": True,
            "holdout_frozen_before_acquisition": True,
            "network_fallback_only_on_shortage": True,
            "source_apply": False,
            "promotion_applied": False,
        },
    }


def _project(root: Path, corpus: str, name: str) -> None:
    project = root / "artifacts" / corpus / "src" / name
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text('[build-system]\nrequires=["wheel"]\n', encoding="utf-8")
    (project / "one.py").write_text(f"PROJECT = {name!r}\n", encoding="utf-8")
    (project / "two.py").write_text("VALUE = 2\n", encoding="utf-8")


def test_index_deduplicates_and_freezes_disjoint_untouched_split(tmp_path: Path) -> None:
    for name in ("a__one", "b__two", "c__three", "d__four", "e__five", "f__six"):
        _project(tmp_path, "github_blind", name)
    _project(tmp_path, "github_copy", "a__one")
    (tmp_path / "artifacts" / "project_development").mkdir()
    (tmp_path / "artifacts" / "project_development" / "used.json").write_text(
        json.dumps({"project": "e__five"}), encoding="utf-8"
    )
    (tmp_path / "artifacts" / "field_trials").mkdir()
    (tmp_path / "artifacts" / "field_trials" / "old.json").write_text(
        json.dumps({"cases": [{"project": "f__six"}]}), encoding="utf-8"
    )

    report = build_corpus_eligibility_index(root=tmp_path, policy=_policy())

    assert report["status"] == "local_corpus_sufficient"
    assert report["summary"]["discovered_copies"] == 7
    assert report["summary"]["unique_projects"] == 6
    assert len(report["acquisition"]) == len(report["holdout"]) == 2
    assert {row["canonical_project"] for row in report["acquisition"]}.isdisjoint(
        row["canonical_project"] for row in report["holdout"]
    )
    assert all(report["checks"].values())


def test_shortage_requests_network_only_after_local_filtering(tmp_path: Path) -> None:
    _project(tmp_path, "github_blind", "a__one")
    (tmp_path / "artifacts" / "project_development").mkdir()
    (tmp_path / "artifacts" / "field_trials").mkdir()

    report = build_corpus_eligibility_index(root=tmp_path, policy=_policy())

    assert report["status"] == "local_corpus_shortage"
    assert report["network_fallback"]["required"] is True
    assert sum(report["shortage"].values()) == 3


def test_policy_rejects_contaminated_holdout_boundary(tmp_path: Path) -> None:
    policy = copy.deepcopy(_policy())
    policy["invariants"]["untouched_only"] = False
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(CorpusEligibilityError, match="invariants are incomplete"):
        load_corpus_eligibility_policy(str(path))

from __future__ import annotations

from pathlib import Path

import runtime.self_development_challenge_external as external


def _candidate(root: Path) -> dict:
    project = root / "external" / "owner__parser"
    (project / ".git").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "parser.py").write_text(
        "def parse(value): return value\n", encoding="utf-8"
    )
    return {
        "project": "owner__parser",
        "owner": "owner",
        "source_url": "https://example.test/owner/parser.git",
        "revision": "a" * 40,
        "project_root": "external/owner__parser",
        "expected_project_type": "library_pure_transform",
    }


def _shortage() -> tuple[list[dict], dict]:
    splits = [{
        "project_type": "library_pure_transform",
        "acquisition": [],
        "holdout": [{"owner": "local", "content_digest": "sha256:local"}],
    }]
    shortages = {"library_pure_transform": {"acquisition": 0, "holdout": 1}}
    return splits, shortages


def test_external_holdout_fills_only_measured_shortage(
    tmp_path: Path, monkeypatch,
) -> None:
    candidate = _candidate(tmp_path)
    monkeypatch.setattr(external, "_git_snapshot", lambda path: {
        "status": "", "revision": "a" * 40,
        "origin": "https://example.test/owner/parser.git",
    })
    splits, shortages = _shortage()

    used = external.fill_external_shortage(
        root=tmp_path, splits=splits, shortages=shortages,
        acquisition_candidates=[], holdout_candidates=[candidate],
        exposed_projects=set(),
    )

    assert len(used) == 1
    assert used[0]["source_kind"] == "targeted_external_holdout"
    assert shortages["library_pure_transform"]["holdout"] == 0
    assert splits[0]["checks"] == {
        "owner_disjoint": True, "content_disjoint": True,
    }


def test_external_holdout_rejects_revision_mismatch(
    tmp_path: Path, monkeypatch,
) -> None:
    candidate = _candidate(tmp_path)
    monkeypatch.setattr(external, "_git_snapshot", lambda path: {
        "status": "", "revision": "b" * 40,
        "origin": "https://example.test/owner/parser.git",
    })
    splits, shortages = _shortage()

    used = external.fill_external_shortage(
        root=tmp_path, splits=splits, shortages=shortages,
        acquisition_candidates=[], holdout_candidates=[candidate],
        exposed_projects=set(),
    )

    assert used == []
    assert shortages["library_pure_transform"]["holdout"] == 1

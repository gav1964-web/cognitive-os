import json
from pathlib import Path
from unittest.mock import patch

from tools.gitlab_blind_corpus import (
    _eligible,
    _project_row,
    _safe_remove_checkout,
    _search_stratum,
    known_projects,
)


def _item(project_id: int, full_name: str, stars: int = 20) -> dict:
    return {
        "id": project_id,
        "path_with_namespace": full_name,
        "http_url_to_repo": f"https://gitlab.com/{full_name}.git",
        "star_count": stars,
        "default_branch": "main",
        "web_url": f"https://gitlab.com/{full_name}",
        "description": "Production Python automation service",
        "topics": ["python"],
        "last_activity_at": "2026-01-01T00:00:00Z",
        "empty_repo": False,
    }


def test_known_projects_excludes_cross_forge_repository_names(tmp_path: Path):
    corpus = tmp_path / "github_blind"
    corpus.mkdir()
    (corpus / "selection.json").write_text(
        json.dumps({"projects": [{"full_name": "owner/unique-engine"}]}), encoding="utf-8"
    )

    names, repos = known_projects(tmp_path)

    assert "owner/unique-engine" in names
    assert "unique-engine" in repos


def test_gitlab_project_row_and_eligibility():
    row = _project_row(_item(7, "group/runtime-engine"))
    policy = {
        "minimum_stars": 10,
        "minimum_recent_year": 2020,
        "excluded_name_tokens": ["tutorial"],
        "excluded_description_tokens": ["mirror of"],
    }

    assert row["full_name"] == "group/runtime-engine"
    assert row["clone_url"].endswith("runtime-engine.git")
    assert _eligible(row, policy) is True


def test_search_stratum_filters_known_repository_mirror():
    policy = {
        "minimum_stars": 10,
        "minimum_recent_year": 2020,
        "maximum_search_pages": 1,
        "excluded_name_tokens": [],
        "excluded_description_tokens": [],
    }
    items = [_item(1, "mirror/known-tool", 100), _item(2, "fresh/new-tool", 50)]
    with patch("tools.gitlab_blind_corpus._search_page", return_value=items):
        rows = _search_stratum(
            {"id": "automation", "queries": ["automation"]}, policy,
            excluded_names=set(), excluded_repos={"known-tool"}, needed=1,
        )

    assert [row["full_name"] for row in rows if row["full_name"] != "mirror/known-tool"] == ["fresh/new-tool"]


def test_safe_remove_checkout_is_limited_to_source_children(tmp_path: Path):
    source = tmp_path / "src"
    checkout = source / "partial"
    checkout.mkdir(parents=True)
    (checkout / "marker").write_text("partial", encoding="utf-8")

    _safe_remove_checkout(source, checkout)

    assert not checkout.exists()

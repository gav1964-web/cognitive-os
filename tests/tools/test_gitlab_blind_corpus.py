import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from tools.gitlab_blind_corpus import (
    _eligible,
    _project_row,
    _safe_remove_checkout,
    _search_page,
    _search_stratum,
    known_projects,
    replace_failed,
    select_corpus,
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


def test_known_projects_includes_effective_replacements(tmp_path: Path):
    corpus = tmp_path / "gitlab_blind"
    corpus.mkdir()
    (corpus / "effective_selection.json").write_text(
        json.dumps({"projects": [{"full_name": "replacement/final-tool"}]}), encoding="utf-8"
    )

    names, repos = known_projects(tmp_path)

    assert "replacement/final-tool" in names
    assert "final-tool" in repos


def test_known_projects_includes_nested_hypothesis_holdouts(tmp_path: Path):
    corpus = tmp_path / "hypothesis_holdouts" / "hvp_test"
    corpus.mkdir(parents=True)
    (corpus / "selection.json").write_text(
        json.dumps({"projects": [{"full_name": "owner/holdout-tool"}]}), encoding="utf-8"
    )

    names, repos = known_projects(tmp_path)

    assert "owner/holdout-tool" in names
    assert "holdout-tool" in repos


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
    with patch("tools.gitlab_corpus_search.search_page", return_value=items):
        rows = _search_stratum(
            {"id": "automation", "queries": ["automation"]}, policy,
            excluded_names=set(), excluded_repos={"known-tool"}, needed=1,
        )

    assert [row["full_name"] for row in rows if row["full_name"] != "mirror/known-tool"] == ["fresh/new-tool"]


def test_search_stratum_batches_multiple_pages():
    policy = {
        "minimum_stars": 1,
        "minimum_recent_year": 2020,
        "maximum_search_pages": 4,
        "search_page_batch_size": 2,
        "excluded_name_tokens": [],
        "excluded_description_tokens": [],
    }
    calls = []

    def page(params, _policy):
        calls.append(int(params["page"]))
        return []

    with patch("tools.gitlab_corpus_search.search_page", side_effect=page):
        _search_stratum(
            {"id": "automation", "queries": ["automation"]}, policy,
            excluded_names=set(), excluded_repos=set(), needed=1,
        )

    assert sorted(calls) == [1, 2, 3, 4]


def test_search_stratum_respects_discovery_round_page_start():
    policy = {
        "minimum_stars": 1, "minimum_recent_year": 2020,
        "maximum_search_pages": 2, "search_page_start": 3,
        "search_page_batch_size": 1, "excluded_name_tokens": [],
        "excluded_description_tokens": [],
    }
    calls = []

    def page(params, _policy):
        calls.append(int(params["page"]))
        return []

    with patch("tools.gitlab_corpus_search.search_page", side_effect=page):
        _search_stratum(
            {"id": "state", "queries": ["state registry"]}, policy,
            excluded_names=set(), excluded_repos=set(), needed=1,
        )

    assert calls == [3, 4]


def test_search_stratum_uses_configured_activity_cursor():
    policy = {
        "minimum_stars": 1,
        "minimum_recent_year": 2020,
        "maximum_search_pages": 1,
        "search_order_by": "last_activity_at",
        "excluded_name_tokens": [],
        "excluded_description_tokens": [],
    }
    captured = []

    def page(params, _policy):
        captured.append(params)
        return [_item(1, "fresh/active-project")]

    with patch("tools.gitlab_corpus_search.search_page", side_effect=page):
        _search_stratum(
            {"id": "active", "queries": ["automation"]}, policy,
            excluded_names=set(), excluded_repos=set(), needed=1,
        )

    assert captured[0]["order_by"] == "last_activity_at"


def test_search_page_turns_repeated_timeout_into_empty_page():
    with (
        patch("tools.gitlab_corpus_search.urllib.request.urlopen", side_effect=TimeoutError),
        patch("tools.gitlab_corpus_search.time.sleep") as sleep,
    ):
        rows = _search_page({"search": "scientific"})

    assert rows == []
    sleep.assert_called_once_with(1)


def test_search_page_exposes_exhausted_rate_limit():
    error = HTTPError("https://gitlab.test", 429, "rate limited", {}, None)
    with (
        patch("tools.gitlab_corpus_search.urllib.request.urlopen", side_effect=error),
        patch("tools.gitlab_corpus_search.time.sleep"),
        pytest.raises(HTTPError, match="429"),
    ):
        _search_page({"search": "scientific"}, {"api_retry_attempts": 2})


def test_selection_redistributes_stratum_shortfall_from_unseen_overflow(tmp_path: Path):
    policy = {
        "projects_per_stratum": 2,
        "minimum_stars": 1,
        "minimum_recent_year": 2020,
        "excluded_name_tokens": [],
        "excluded_description_tokens": [],
        "strata": [
            {"id": "scarce", "queries": ["scarce"]},
            {"id": "plentiful", "queries": ["plentiful"]},
        ],
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    rows = [
        [_project_row(_item(1, "group/scarce"))],
        [_project_row(_item(index, f"group/plentiful-{index}")) for index in (2, 3, 4)],
    ]

    with patch("tools.gitlab_blind_corpus._search_stratum", side_effect=rows):
        result = select_corpus(tmp_path, tmp_path / "corpus", 1, policy_path)

    selection = json.loads(Path(result["selection_path"]).read_text(encoding="utf-8"))
    assert selection["project_count"] == 4
    assert selection["requested_by_stratum"] == {"scarce": 2, "plentiful": 2}
    assert selection["selected_by_stratum"] == {"plentiful": 3, "scarce": 1}


def test_safe_remove_checkout_is_limited_to_source_children(tmp_path: Path):
    source = tmp_path / "src"
    checkout = source / "partial"
    checkout.mkdir(parents=True)
    (checkout / "marker").write_text("partial", encoding="utf-8")

    _safe_remove_checkout(source, checkout)

    assert not checkout.exists()


def test_replace_failed_claims_each_replacement_once(tmp_path: Path):
    corpus = tmp_path / "artifacts" / "corpus"
    corpus.mkdir(parents=True)
    policy = {
        "minimum_stars": 1,
        "minimum_recent_year": 2020,
        "excluded_name_tokens": [],
        "excluded_description_tokens": [],
        "strata": [{"id": "automation", "queries": ["automation"]}],
    }
    originals = [
        {**_project_row(_item(index, f"old/project-{index}")), "stratum": "automation"}
        for index in (1, 2)
    ]
    (corpus / "selection.json").write_text(
        json.dumps({"projects": originals, "policy": policy}), encoding="utf-8"
    )
    (corpus / "clone_report.json").write_text(
        json.dumps({"results": [
            {"full_name": row["full_name"], "status": "clone_failed"}
            for row in originals
        ]}),
        encoding="utf-8",
    )
    candidates = [
        _project_row(_item(index + 10, f"new/replacement-{index}"))
        for index in (1, 2)
    ]

    def cloned(source_dir, project, *, force):
        destination = source_dir / project["full_name"].replace("/", "__")
        destination.mkdir(parents=True, exist_ok=True)
        return {"full_name": project["full_name"], "status": "ok", "path": destination.as_posix()}

    with (
        patch("tools.gitlab_blind_corpus._search_stratum", return_value=candidates),
        patch("tools.gitlab_blind_corpus._clone_one", side_effect=cloned),
    ):
        report = replace_failed(tmp_path, corpus)

    effective = json.loads((corpus / "effective_selection.json").read_text(encoding="utf-8"))
    assert report["project_count"] == 2
    assert [row["full_name"] for row in effective["projects"]] == [
        "new/replacement-1", "new/replacement-2",
    ]

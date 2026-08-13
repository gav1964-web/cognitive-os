import json
from unittest.mock import patch

from tools.github_blind_corpus import _checkout_ready, _eligible, _project_row, _search_stratum, _search_with_gh, known_projects


def test_known_projects_reads_only_frozen_top_level_selections(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "selection.json").write_text(
        json.dumps({"projects": [{"full_name": "Owner/Repo"}]}), encoding="utf-8"
    )
    nested = corpus / "src" / "other"
    nested.mkdir(parents=True)
    (nested / "selection.json").write_text(
        json.dumps({"projects": [{"full_name": "Ignored/Nested"}]}), encoding="utf-8"
    )

    assert known_projects(tmp_path) == {"owner/repo"}


def test_project_row_keeps_reproducibility_metadata():
    row = _project_row(
        {
            "full_name": "Owner/Repo",
            "clone_url": "https://github.com/Owner/Repo.git",
            "stargazers_count": 123,
            "size": 456,
            "default_branch": "main",
            "html_url": "https://github.com/Owner/Repo",
            "description": "Example",
        }
    )

    assert row["full_name"] == "Owner/Repo"
    assert row["stars"] == 123
    assert row["size_kb"] == 456


def test_production_filter_rejects_learning_collections_and_keeps_services():
    policy = {
        "excluded_name_tokens": ["awesome", "blogs", "interview-questions", "projects", "resources", "template", "tutorial", "udacity"],
        "excluded_description_tokens": ["course", "collection of", "curated list", "example end to end", "examples of", "interview questions"],
        "production_signal_tokens": ["api", "service", "library"],
    }

    assert not _eligible({"full_name": "org/awesome-api", "description": "API list", "topics": []}, policy)
    assert not _eligible({"full_name": "org/ml", "description": "course exercises", "topics": ["library"]}, policy)
    assert not _eligible({"full_name": "org/api-template", "description": "Production API", "topics": []}, policy)
    assert not _eligible({"full_name": "org/ml", "description": "Examples of ML algorithms", "topics": []}, policy)
    assert not _eligible({"full_name": "org/data-blogs", "description": "Data library", "topics": []}, policy)
    assert not _eligible({"full_name": "org/catalog", "description": "A curated list of APIs", "topics": []}, policy)
    assert not _eligible({"full_name": "org/data-projects", "description": "Data platform", "topics": []}, policy)
    assert not _eligible({"full_name": "org/questions", "description": "200 interview questions", "topics": []}, policy)
    assert _eligible({"full_name": "org/payments", "description": "Production API service", "topics": []}, policy)


def test_search_uses_authenticated_gh_transport_when_token_exists():
    policy = {"minimum_stars": 1, "maximum_size_kb": 10}
    with patch.dict("os.environ", {"GITHUB_TOKEN": "secret-token"}), patch(
        "tools.github_blind_corpus._search_with_gh", return_value={"items": []}
    ) as search:
        assert _search_stratum({"queries": ["topic:sdk"]}, policy) == []

    assert search.call_count == 1


def test_search_paginates_only_until_enough_unseen_projects_exist():
    policy = {
        "minimum_stars": 1, "maximum_size_kb": 10, "maximum_search_pages": 3,
        "production_signal_tokens": ["sdk"],
    }
    items = lambda names: {
        "items": [
            {"full_name": name, "clone_url": "url", "stargazers_count": 10, "size": 2,
             "description": "production sdk", "topics": []}
            for name in names
        ]
    }
    with patch("tools.github_blind_corpus._search_page", side_effect=[items(["old/sdk"]), items(["new/sdk1", "new/sdk2"])]) as search:
        rows = _search_stratum(
            {"queries": ["topic:sdk"]}, policy, excluded={"old/sdk"}, needed=2
        )

    assert {row["full_name"] for row in rows} == {"old/sdk", "new/sdk1", "new/sdk2"}
    assert search.call_count == 2
    assert search.call_args_list[1].args[0]["page"] == "2"


def test_authenticated_search_does_not_put_token_in_command():
    completed = type("Completed", (), {"returncode": 0, "stdout": '{"items": []}', "stderr": ""})()
    with patch("subprocess.run", return_value=completed) as run:
        assert _search_with_gh({"q": "topic:sdk", "per_page": "50"}) == {"items": []}

    command = run.call_args.args[0]
    assert "secret-token" not in " ".join(command)


def test_authenticated_search_retries_one_rate_limit_window():
    limited = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "API rate limit exceeded"})()
    success = type("Completed", (), {"returncode": 0, "stdout": '{"items": []}', "stderr": ""})()
    with patch("subprocess.run", side_effect=[limited, success]) as run, patch("time.sleep") as sleep:
        assert _search_with_gh({"q": "topic:cli"}) == {"items": []}

    assert run.call_count == 2
    sleep.assert_called_once_with(65)


def test_checkout_ready_requires_clean_git_status(tmp_path):
    completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    with patch("subprocess.run", return_value=completed) as run:
        assert _checkout_ready(tmp_path)
    assert run.call_args.args[0][-2:] == ["status", "--porcelain"]

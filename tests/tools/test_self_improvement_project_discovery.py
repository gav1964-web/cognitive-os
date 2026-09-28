import json
from pathlib import Path
from unittest.mock import patch

from tools.self_improvement_project_discovery import (
    _holdout_directory, _policy, _provider_queries, discover_gitlab_holdouts,
    _resource_screen, discover_holdouts,
)


def _project(name: str) -> dict:
    return {
        "full_name": name, "clone_url": f"https://gitlab.com/{name}.git",
        "stars": 10, "description": "Active Python project",
        "last_activity_at": "2026-01-01T00:00:00Z", "empty_repo": False,
    }


def test_discovery_freezes_and_reuses_hypothesis_holdouts(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "gitlab_blind_corpus_strata.json").write_text(json.dumps({
        "minimum_stars": 3, "minimum_recent_year": 2020,
        "excluded_name_tokens": [], "excluded_description_tokens": [],
        "search_workers": 2,
    }), encoding="utf-8")
    plan = {
        "provider": "gitlab", "hypothesis_id": "hvp_test",
        "portable_signature": "side_effectful_target|memory_state|no_value_return",
        "queries": ["state management"], "maximum_search_pages": 1,
        "maximum_projects": 2, "excluded_projects": ["owner__source"],
    }
    candidates = [_project("fresh/one"), _project("fresh/two")]

    def clone(source_dir, project, *, force):
        path = source_dir / project["full_name"].replace("/", "__")
        path.mkdir(parents=True, exist_ok=True)
        return {"full_name": project["full_name"], "status": "ok", "path": path.as_posix()}

    with (
        patch("tools.self_improvement_project_discovery._search_gitlab", return_value=candidates) as search,
        patch("tools.self_improvement_project_discovery._clone_gitlab", side_effect=clone),
    ):
        first = discover_gitlab_holdouts(tmp_path, plan)
        second = discover_gitlab_holdouts(tmp_path, plan)

    assert [path.name for path in first] == ["fresh__one", "fresh__two"]
    assert second == first
    search.assert_called_once()
    selection = json.loads((
        tmp_path / "artifacts" / "hypothesis_holdouts" / "hvp_test" / "selection.json"
    ).read_text(encoding="utf-8"))
    assert selection["selection_frozen"] is True


def test_holdout_cache_is_scoped_to_query_window(tmp_path: Path):
    base = {"hypothesis_id": "hvp_test", "search_page_start": 1, "query_page_end": 2}

    first = _holdout_directory(tmp_path, {**base, "queries": ["event bus"]})
    repeated = _holdout_directory(tmp_path, {**base, "queries": ["event bus"]})
    next_query = _holdout_directory(tmp_path, {**base, "queries": ["hook manager"]})
    next_page = _holdout_directory(
        tmp_path, {**base, "queries": ["event bus"], "search_page_start": 3, "query_page_end": 4}
    )

    assert first == repeated
    assert len({first, next_query, next_page}) == 3


def test_discovery_falls_back_from_gitlab_to_github(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("gitlab_blind_corpus_strata.json", "github_blind_corpus_strata.json"):
        (config / name).write_text(json.dumps({
            "minimum_stars": 3, "minimum_recent_year": 2020,
            "maximum_size_kb": 30000, "excluded_name_tokens": [],
            "excluded_description_tokens": [], "production_signal_tokens": [],
            "search_workers": 2,
        }), encoding="utf-8")
    plan = {
        "providers": ["gitlab", "github"], "hypothesis_id": "hvp_fallback",
        "portable_signature": "side_effectful_target|memory_state|no_value_return",
        "queries": ["state management"], "maximum_search_pages": 1,
        "minimum_projects": 2, "maximum_projects": 2, "excluded_projects": [],
    }
    candidates = [_project("github/one"), _project("github/two")]

    def clone(source_dir, project, *, force):
        path = source_dir / project["full_name"].replace("/", "__")
        path.mkdir(parents=True, exist_ok=True)
        return {"full_name": project["full_name"], "status": "ok", "path": path.as_posix()}

    with (
        patch("tools.self_improvement_project_discovery._search_gitlab", side_effect=RuntimeError("429")),
        patch("tools.self_improvement_project_discovery._search_github", return_value=candidates),
        patch("tools.self_improvement_project_discovery._clone_github", side_effect=clone),
    ):
        projects = discover_holdouts(tmp_path, plan)

    assert [path.name for path in projects] == ["github__one", "github__two"]
    selection = json.loads((
        tmp_path / "artifacts" / "hypothesis_holdouts" / "hvp_fallback" / "selection.json"
    ).read_text(encoding="utf-8"))
    assert selection["provider_attempts"] == [
        {"provider": "gitlab", "status": "failed", "error": "RuntimeError: 429"},
        {"provider": "github", "status": "ok", "selected": 2},
    ]
    assert {row["provider"] for row in selection["projects"]} == {"github"}


def test_discovery_reapplies_eligibility_before_claiming_candidates(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    for name in ("gitlab_blind_corpus_strata.json", "github_blind_corpus_strata.json"):
        (config / name).write_text(json.dumps({
            "minimum_stars": 3, "minimum_recent_year": 2020,
            "maximum_size_kb": 30000, "excluded_name_tokens": [],
            "excluded_description_tokens": [], "production_signal_tokens": [],
            "search_workers": 2,
        }), encoding="utf-8")
    plan = {
        "providers": ["gitlab", "github"], "hypothesis_id": "hvp_eligibility",
        "portable_signature": "side_effectful_target|memory_state|no_value_return",
        "queries": ["state management"], "maximum_search_pages": 1,
        "minimum_projects": 2, "maximum_projects": 2, "excluded_projects": [],
    }
    invalid = {**_project("gitlab/invalid"), "stars": 2}
    valid = _project("gitlab/valid")
    github = _project("github/fallback")

    def clone(source_dir, project, *, force):
        path = source_dir / project["full_name"].replace("/", "__")
        path.mkdir(parents=True, exist_ok=True)
        return {"full_name": project["full_name"], "status": "ok", "path": path.as_posix()}

    with (
        patch("tools.self_improvement_project_discovery._search_gitlab", return_value=[invalid, valid]),
        patch("tools.self_improvement_project_discovery._search_github", return_value=[github]),
        patch("tools.self_improvement_project_discovery._clone_gitlab", side_effect=clone),
        patch("tools.self_improvement_project_discovery._clone_github", side_effect=clone),
    ):
        discover_holdouts(tmp_path, plan)

    selection = json.loads((
        tmp_path / "artifacts" / "hypothesis_holdouts" / "hvp_eligibility" / "selection.json"
    ).read_text(encoding="utf-8"))
    assert [row["full_name"] for row in selection["projects"]] == [
        "gitlab/valid", "github/fallback",
    ]
    assert selection["provider_attempts"] == [
        {"provider": "gitlab", "status": "ok", "selected": 1},
        {"provider": "github", "status": "ok", "selected": 1},
    ]


def test_discovery_freezes_empty_round_without_claiming_provider_failure(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "gitlab_blind_corpus_strata.json").write_text(json.dumps({
        "minimum_stars": 3, "minimum_recent_year": 2020,
        "excluded_name_tokens": [], "excluded_description_tokens": [],
        "search_workers": 2,
    }), encoding="utf-8")
    plan = {
        "providers": ["gitlab"], "hypothesis_id": "hvp_empty",
        "portable_signature": "side_effectful_target|memory_state|no_value_return",
        "queries": ["state registry"], "maximum_search_pages": 1,
        "minimum_projects": 2, "maximum_projects": 2, "excluded_projects": [],
    }

    with patch("tools.self_improvement_project_discovery._search_gitlab", return_value=[]):
        projects = discover_holdouts(tmp_path, plan)

    assert projects == []
    selection = json.loads((
        tmp_path / "artifacts" / "hypothesis_holdouts" / "hvp_empty" / "selection.json"
    ).read_text(encoding="utf-8"))
    assert selection["projects"] == []
    assert selection["provider_attempts"] == [{"provider": "gitlab", "status": "ok", "selected": 0}]


def test_hypothesis_provider_policy_override_is_separate_from_release_policy(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "github_blind_corpus_strata.json").write_text(json.dumps({
        "minimum_stars": 300, "maximum_size_kb": 30000,
    }), encoding="utf-8")

    policy = _policy(tmp_path, "github_blind_corpus_strata.json", {
        "maximum_search_pages": 2,
        "provider_policy_overrides": {"github": {"minimum_stars": 20}},
    })

    assert policy["minimum_stars"] == 20
    release = json.loads((config / "github_blind_corpus_strata.json").read_text(encoding="utf-8"))
    assert release["minimum_stars"] == 300


def test_provider_queries_translate_github_qualifiers_for_gitlab():
    plan = {"queries": [
        "topic:state-management", "global state in:name,description",
        "state registry command handler",
    ]}

    assert _provider_queries(plan, "gitlab") == [
        "state management", "global state", "state registry command handler",
    ]
    assert _provider_queries(plan, "github") == plan["queries"]


def test_discovery_structurally_screens_wide_metadata_pool(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "gitlab_blind_corpus_strata.json").write_text(json.dumps({
        "minimum_stars": 3, "minimum_recent_year": 2020,
        "excluded_name_tokens": [], "excluded_description_tokens": [],
        "search_workers": 2,
    }), encoding="utf-8")
    plan = {
        "providers": ["gitlab"], "hypothesis_id": "hvp_screen",
        "portable_signature": "side_effectful_target|memory_state|no_value_return",
        "queries": ["state management"], "maximum_search_pages": 1,
        "minimum_projects": 2, "maximum_projects": 2,
        "candidate_pool_projects": 3, "excluded_projects": [],
        "structural_prescreen": {
            "enabled": True, "maximum_shortlist_projects": 1,
            "minimum_shortlist_projects": 1, "maximum_python_files": 10,
            "maximum_functions": 50, "excluded_directories": [],
        },
    }
    candidates = [_project("fresh/pure"), _project("fresh/state"), _project("fresh/other")]

    def clone(source_dir, project, *, force):
        path = source_dir / project["full_name"].replace("/", "__")
        path.mkdir(parents=True, exist_ok=True)
        source = (
            "class Store:\n    def update(self, value):\n        self.values.append(value)\n"
            if project["full_name"] == "fresh/state"
            else "def normalize(value):\n    return value.strip()\n"
        )
        (path / "module.py").write_text(source, encoding="utf-8")
        return {"full_name": project["full_name"], "status": "ok", "path": path.as_posix()}

    with (
        patch("tools.self_improvement_project_discovery._search_gitlab", return_value=candidates) as search,
        patch("tools.self_improvement_project_discovery._clone_gitlab", side_effect=clone),
    ):
        projects = discover_holdouts(tmp_path, plan)
        repeated = discover_holdouts(tmp_path, plan)

    assert [path.name for path in projects] == ["fresh__state"]
    assert repeated == projects
    search.assert_called_once()
    directory = tmp_path / "artifacts" / "hypothesis_holdouts" / "hvp_screen"
    selection = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    screen = json.loads((directory / "structural_screen.json").read_text(encoding="utf-8"))
    assert len(selection["projects"]) == 3
    assert screen["candidate_project_count"] == 3
    assert screen["selected_projects"] == ["fresh__state"]
    assert plan["retrieval_targets"] == {"fresh__state": "module.py:Store.update"}
    assert screen["retrieval_evidence_only"] is True
    assert screen["screening_frozen"] is True


def test_resource_screen_rejects_oversized_generated_python(tmp_path: Path):
    directory = tmp_path / "holdout"
    accepted = tmp_path / "accepted"
    oversized = tmp_path / "oversized"
    directory.mkdir(); accepted.mkdir(); oversized.mkdir()
    (accepted / "module.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (oversized / "generated.py").write_text("x = 1\n" * 1000, encoding="utf-8")

    projects = _resource_screen(
        directory, [accepted, oversized],
        {"maximum_project_python_file_bytes": 100},
    )

    assert projects == [accepted]
    report = json.loads((directory / "resource_screen.json").read_text(encoding="utf-8"))
    assert report["accepted_project_count"] == 1
    assert report["rejected"][0]["project"] == "oversized"
    assert report["rejected"][0]["reason"] == "python_file_resource_budget_exceeded"

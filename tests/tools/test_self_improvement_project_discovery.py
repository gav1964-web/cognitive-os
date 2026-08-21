import json
from pathlib import Path
from unittest.mock import patch

from tools.self_improvement_project_discovery import discover_gitlab_holdouts


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
        patch("tools.self_improvement_project_discovery._search_stratum", return_value=candidates) as search,
        patch("tools.self_improvement_project_discovery._clone_one", side_effect=clone),
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

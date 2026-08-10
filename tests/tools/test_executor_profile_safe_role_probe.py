from __future__ import annotations

from pathlib import Path

from tools.executor_profile_safe_role_probe import run_profile_safe_role_probe


def test_executor_profile_safe_role_probe_runs_role_chain(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "helpers.py").write_text(
        "def normalize_name(name: str) -> str:\n"
        "    return name\n\n"
        "def sort_items(items: list) -> list:\n"
        "    return items\n",
        encoding="utf-8",
    )

    report = run_profile_safe_role_probe(root=tmp_path, projects_dir=projects, label="test", limit=5)

    assert report["status"] == "ok"
    assert report["summary"]["accepted"] == 1
    assert report["summary"]["profiles"] == {"normalize_string": 1}
    assert report["summary"]["patch_transforms"] == {"strip_lower": 1}

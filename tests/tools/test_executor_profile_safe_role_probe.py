from __future__ import annotations

from pathlib import Path

from tools.executor_profile_safe_role_probe import _discover_rows, run_profile_safe_role_probe


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


def test_discovery_finds_nested_registered_operator(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "helpers.py").write_text(
        "def outer():\n"
        "    def first_item(value):\n"
        "        return value[0]\n"
        "    return first_item\n",
        encoding="utf-8",
    )

    rows = _discover_rows(tmp_path, limit=5, max_per_project=5)

    assert [(row["source_target"], row["operator_id"]) for row in rows] == [
        ("helpers.py:first_item", "first_item")
    ]
    assert rows[0]["mutation_source"] == "real_operator_replaced_with_identity"


def test_discovery_allows_defaults_for_exact_registered_operator(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "helpers.py").write_text(
        "def is_console(value=str):\n"
        "    return value.startswith('CON.1')\n",
        encoding="utf-8",
    )

    rows = _discover_rows(tmp_path, limit=5, max_per_project=5)

    assert [(row["source_target"], row["operator_id"]) for row in rows] == [
        ("helpers.py:is_con1", "starts_with_con1")
    ]

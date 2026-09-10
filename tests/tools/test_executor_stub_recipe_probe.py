from __future__ import annotations

from pathlib import Path

from tools.executor_stub_recipe_probe import run_stub_probe


def test_executor_stub_recipe_probe_uses_real_source_derived_stub(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "api.py").write_text("def placeholder():\n    pass\n", encoding="utf-8")

    report = run_stub_probe(root=tmp_path, projects_dir=projects, limit=5, label="test")

    assert report["status"] == "ok"
    assert report["summary"]["accepted"] == 1
    assert report["summary"]["patch_reasons"] == {"return_literal_stub_synthesized": 1}
    assert report["summary"]["patch_quality_levels"] == {"contract_backed_return_literal": 1}


def test_executor_stub_recipe_probe_can_run_full_repo_mode(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "api.py").write_text("def placeholder():\n    pass\n", encoding="utf-8")

    report = run_stub_probe(root=tmp_path, projects_dir=projects, limit=5, label="test", mode="full-repo")

    assert report["status"] == "ok"
    assert report["invariants"]["mode"] == "full-repo"
    assert report["cases"][0]["source_target"] == "demo/api.py:placeholder"


def test_executor_stub_recipe_probe_full_repo_skips_risky_entrypoints(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "api.py").write_text(
        "@decorator\n"
        "def decorated():\n"
        "    pass\n"
        "\n"
        "def cli():\n"
        "    pass\n"
        "\n"
        "def leaf_placeholder():\n"
        "    pass\n",
        encoding="utf-8",
    )

    report = run_stub_probe(root=tmp_path, projects_dir=projects, limit=5, label="test", mode="full-repo")

    assert report["summary"]["accepted"] == 1
    assert report["cases"][0]["source_target"] == "demo/api.py:leaf_placeholder"


def test_executor_stub_recipe_probe_can_find_notimplemented_placeholder(tmp_path: Path):
    projects = tmp_path / "projects"
    project = projects / "demo"
    project.mkdir(parents=True)
    (project / "api.py").write_text("def placeholder():\n    raise NotImplementedError\n", encoding="utf-8")

    report = run_stub_probe(root=tmp_path, projects_dir=projects, limit=5, label="test", placeholder_kind="notimplemented")

    assert report["status"] == "ok"
    assert report["summary"]["patch_reasons"] == {"return_literal_notimplemented_synthesized": 1}

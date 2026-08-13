from pathlib import Path

from runtime.role_foundation_field_trial import discover_python_projects


def test_discovery_keeps_git_checkout_without_root_manifest_as_one_project(tmp_path: Path):
    project = tmp_path / "monorepo"
    (project / ".git").mkdir(parents=True)
    (project / "docker").mkdir()
    (project / "docker" / "requirements.txt").write_text("gunicorn\n", encoding="utf-8")
    (project / "docker" / "webserver_config.py").write_text("bind = '0.0.0.0'\n", encoding="utf-8")

    found = discover_python_projects([project])

    assert found == [project.resolve()]

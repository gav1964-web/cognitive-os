from pathlib import Path

from runtime.source_dependency_readiness import source_dependency_readiness


def test_dependency_readiness_follows_local_imports_without_importing_project(tmp_path: Path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "entry.py").write_text("from pkg.helper import run\n", encoding="utf-8")
    (project / "pkg" / "helper.py").write_text("import definitely_missing_cognitive_os_dep\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "pkg/entry.py")

    assert readiness["status"] == "missing_external"
    assert readiness["missing_external_modules"] == ["definitely_missing_cognitive_os_dep"]
    assert "pkg.helper" in readiness["local_imports"]


def test_dependency_readiness_treats_stdlib_and_local_modules_as_ready(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "entry.py")

    assert readiness["status"] == "ready"
    assert readiness["missing_external_modules"] == []

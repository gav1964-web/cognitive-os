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


def test_dependency_readiness_resolves_absolute_import_from_src_layout(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "sample_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "entry.py").write_text("from sample_pkg.helper import VALUE\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "src/sample_pkg/entry.py")

    assert readiness["status"] == "ready"
    assert "sample_pkg.helper" in readiness["local_imports"]


def test_dependency_readiness_resolves_package_from_nested_manifest_root(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "mcp" / "tickdb_mcp"
    package.mkdir(parents=True)
    (project / "mcp" / "pyproject.toml").write_text("[project]\nname='tickdb-mcp'\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "entry.py").write_text("from tickdb_mcp.helper import VALUE\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "mcp/tickdb_mcp/entry.py")

    assert readiness["status"] == "ready"
    assert "tickdb_mcp.helper" in readiness["local_imports"]


def test_dependency_readiness_accepts_configured_python2_stdlib_aliases(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text("import ConfigParser\nimport urllib2\nimport urlparse\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "entry.py")

    assert readiness["status"] == "ready"


def test_dependency_readiness_resolves_local_namespace_package(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "sample_pkg"
    package.mkdir(parents=True)
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / "entry.py").write_text("from src import sample_pkg\n", encoding="utf-8")

    readiness = source_dependency_readiness(project, "entry.py")

    assert readiness["status"] == "ready"
    assert "src" in readiness["local_imports"]


def test_dependency_readiness_ignores_type_checking_imports(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import definitely_missing_cognitive_os_dep\n",
        encoding="utf-8",
    )

    readiness = source_dependency_readiness(project, "entry.py")

    assert readiness["status"] == "ready"
    assert readiness["missing_external_modules"] == []


def test_dependency_readiness_ignores_qualified_type_checking_imports(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text(
        "import typing\n"
        "if typing.TYPE_CHECKING:\n"
        "    import definitely_missing_cognitive_os_dep\n",
        encoding="utf-8",
    )

    readiness = source_dependency_readiness(project, "entry.py")

    assert readiness["status"] == "ready"


def test_function_readiness_ignores_unused_module_dependency(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text(
        "import definitely_missing_cognitive_os_dep\n\n"
        "def normalize(value):\n    return value.strip()\n\n"
        "def remote(value):\n    return definitely_missing_cognitive_os_dep.convert(value)\n",
        encoding="utf-8",
    )

    normalize = source_dependency_readiness(project, "entry.py", "normalize")
    remote = source_dependency_readiness(project, "entry.py", "remote")

    assert normalize["status"] == "ready"
    assert normalize["analysis"] == "function_scoped_static_import_graph"
    assert remote["missing_external_modules"] == ["definitely_missing_cognitive_os_dep"]


def test_function_readiness_detects_import_inside_selected_callable(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "entry.py").write_text(
        "def select_backend():\n"
        "    from definitely_missing_cognitive_os_dep import backend\n"
        "    return backend\n",
        encoding="utf-8",
    )

    readiness = source_dependency_readiness(project, "entry.py", "select_backend")

    assert readiness["status"] == "missing_external"
    assert readiness["missing_external_modules"] == ["definitely_missing_cognitive_os_dep"]

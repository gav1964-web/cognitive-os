from __future__ import annotations

from pathlib import Path

import pytest

from tools.project_context import check_manifest, context, markdown, select_subsystems


def fixture_manifest(root: Path) -> dict:
    (root / "brief.md").write_text("Purpose and limits", encoding="utf-8")
    (root / "source").mkdir()
    (root / "source" / "main.py").write_text("import pathlib\n", encoding="utf-8")
    return {"subsystems": {"sample": {
        "purpose": "Sample", "brief": "brief.md", "entrypoints": ["source/main.py"],
        "contracts": [], "tests": [], "dependencies": [], "paths": ["source/*"],
        "commands": ["python -m pytest"],
    }}, "search_roots": ["source"], "packages": [
        {"source": "source", "allowed_import_roots": ["sample"]},
    ]}


@pytest.mark.parametrize("statement", ["import runtime.schema", "from plugins import x",
                                         "import importlib\nimportlib.import_module('tools.secret')",
                                         "__import__(user_input)"])
def test_boundary_check_rejects_application_and_unresolved_dynamic_imports(tmp_path, statement):
    manifest = fixture_manifest(tmp_path)
    (tmp_path / "source/main.py").write_text(statement, encoding="utf-8")
    assert check_manifest(tmp_path, manifest)


def test_missing_references_and_dependencies_are_visible(tmp_path):
    manifest = fixture_manifest(tmp_path)
    spec = manifest["subsystems"]["sample"]
    spec["contracts"] = ["missing.json"]
    spec["dependencies"] = ["unknown"]
    errors = check_manifest(tmp_path, manifest)
    assert any("missing.json" in error for error in errors)
    assert any("unknown dependency" in error for error in errors)


def test_context_selects_scope_without_reading_unrelated_files(tmp_path):
    manifest = fixture_manifest(tmp_path)
    (tmp_path / "config.json").write_text("do not include", encoding="utf-8")
    names = select_subsystems(tmp_path, manifest, [], ["source/main.py"])
    output = markdown(tmp_path, context(tmp_path, manifest, names))
    assert names == ["sample"]
    assert "Purpose and limits" in output and "source/main.py" in output
    assert "do not include" not in output
    assert check_manifest(tmp_path, manifest) == []


@pytest.mark.parametrize("path", ["../outside.py", "unmapped.py"])
def test_path_selection_does_not_guess_or_escape_root(tmp_path, path):
    with pytest.raises(ValueError):
        select_subsystems(tmp_path, fixture_manifest(tmp_path), [], [path])

from pathlib import Path

import pytest

from plugins.scan_project_tree.src.main import run


def test_scan_project_tree_skips_common_noise(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/.venv").mkdir(parents=True)
    Path("project/src").mkdir()
    Path("project/src/app.py").write_text("print('ok')", encoding="utf-8")
    Path("project/requirements.txt").write_text("pytest==1.0.0", encoding="utf-8")
    Path("project/.venv/ignored.py").write_text("x", encoding="utf-8")

    result = run({"path": "project"})

    assert result["counts"]["files"] == 2
    assert "requirements.txt" in result["notable_files"]
    assert [item["path"] for item in result["files"]] == ["requirements.txt", "src/app.py"]
    assert result["extensions"] == {".py": 1, ".txt": 1}


def test_scan_project_tree_rejects_out_of_scope_path():
    with pytest.raises(ValueError):
        run({"path": "C:/Windows"})

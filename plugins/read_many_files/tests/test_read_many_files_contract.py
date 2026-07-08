from pathlib import Path

from plugins.read_many_files.src.main import run


def test_read_many_files_reads_limited_text_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/a.py").write_text("print('a')", encoding="utf-8")
    Path("project/b.bin").write_bytes(b"\x00\x01")
    Path("project/large.txt").write_text("x" * 20, encoding="utf-8")

    result = run({"root": "project", "paths": ["a.py", "b.bin", "large.txt"], "max_bytes_per_file": 10})

    assert result["files"][0]["path"] == "a.py"
    assert {item["reason"] for item in result["skipped"]} == {"non_text_extension", "too_large"}


def test_read_many_files_auto_discovers_high_value_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/app").mkdir(parents=True)
    Path("project/tools").mkdir()
    Path("project/README.md").write_text("# Project\n", encoding="utf-8")
    Path("project/requirements.txt").write_text("fastapi==1.0\n", encoding="utf-8")
    Path("project/app/server.py").write_text("print('server')\n", encoding="utf-8")
    Path("project/tools/helper.py").write_text("print('helper')\n", encoding="utf-8")

    result = run({"root": "project", "auto_discover": True, "max_files": 3})

    assert [item["path"] for item in result["files"]] == ["README.md", "requirements.txt", "app/server.py"]


def test_read_many_files_auto_discovers_readme_rst(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/README.rst").write_text("Project\n=======\n", encoding="utf-8")
    Path("project/CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    Path("project/pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    result = run({"root": "project", "auto_discover": True, "max_files": 2})

    assert [item["path"] for item in result["files"]] == ["README.rst", "pyproject.toml"]

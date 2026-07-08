from pathlib import Path

from plugins.list_files.src.main import run


def test_list_files_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("a").mkdir()
    Path("a/one.txt").write_text("1", encoding="utf-8")
    assert run({"path": "a"}) == {"files": ["a/one.txt"]}

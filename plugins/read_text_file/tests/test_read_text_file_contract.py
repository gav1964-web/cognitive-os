from pathlib import Path

from plugins.read_text_file.src.main import run


def test_read_text_file_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("sample.txt").write_text("hello", encoding="utf-8")
    assert run({"path": "sample.txt"}) == {"text": "hello"}

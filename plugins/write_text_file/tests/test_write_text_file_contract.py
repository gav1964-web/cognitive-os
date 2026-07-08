from pathlib import Path

from plugins.write_text_file.src.main import run


def test_write_text_file_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run({"path": "out/sample.txt", "text": "hello"}) == {"path": "out/sample.txt"}
    assert Path("out/sample.txt").read_text(encoding="utf-8") == "hello"

from pathlib import Path

from plugins.save_json.src.main import run


def test_save_json_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = Path("out.json")
    result = run({"data": {"title": "Hello"}, "path": str(target)})
    assert Path(result["path"]).exists()

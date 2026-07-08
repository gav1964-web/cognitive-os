from pathlib import Path

from plugins.extract_runtime_commands.src.main import run


def test_extract_runtime_commands_detects_run_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project").mkdir()
    Path("project/RUN_MAP.bat").write_text("@echo off\npython app.py\npause\n", encoding="utf-8")

    result = run({"root": "project"})

    assert result["commands"][0]["path"] == "RUN_MAP.bat"
    assert result["commands"][0]["purpose"] == "run_application"
    assert "python app.py" in result["commands"][0]["commands"]

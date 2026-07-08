from pathlib import Path

from plugins.detect_project_stack.src.main import run


def test_detect_project_stack_reports_python_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/static").mkdir(parents=True)
    Path("project/map_install_package").mkdir(parents=True)
    Path("project/app.py").write_text("from flask import Flask", encoding="utf-8")
    Path("project/map_install_package/app.py").write_text("from flask import Flask", encoding="utf-8")
    Path("project/map_install_package/RUN_MAP.bat").write_text("python app.py", encoding="utf-8")
    Path("project/requirements.txt").write_text("flask==3.0.0\npandas==2.0.0\n", encoding="utf-8")
    Path("project/RUN_MAP.bat").write_text("python app.py", encoding="utf-8")
    Path("project/static/app.js").write_text("console.log('x')", encoding="utf-8")

    result = run({"path": "project"})

    assert "app.py" in result["entrypoints"]
    assert "map_install_package/app.py" not in result["entrypoints"]
    assert "RUN_MAP.bat" in result["scripts"]
    assert "map_install_package/RUN_MAP.bat" not in result["scripts"]
    assert result["dependency_files"][0]["dependencies"] == ["flask", "pandas"]
    assert "Flask-like Python web app" in result["frameworks"]
    assert {"language": "Python", "files": 1} in result["languages"]


def test_detect_project_stack_ignores_context_entrypoints(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("project/tests/testserver").mkdir(parents=True)
    Path("project/tests/testserver/server.py").write_text("print('test server')\n", encoding="utf-8")
    Path("project/src/pkg").mkdir(parents=True)
    Path("project/src/pkg/__init__.py").write_text("", encoding="utf-8")
    Path("project/noxfile.py").write_text("", encoding="utf-8")

    result = run({"path": "project"})

    assert result["entrypoints"] == []

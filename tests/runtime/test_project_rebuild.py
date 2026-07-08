from __future__ import annotations

from pathlib import Path

from runtime.project_rebuild import compare_rebuild, write_rebuild_scaffold
from runtime.project_probe_env import prepare_probe_env, probe_env_readiness
from runtime.programmer_field_trial import _verdict


def test_rebuild_scaffold_preserves_map_shape(tmp_path: Path):
    source = tmp_path / "map"
    source.mkdir()
    (source / "app.py").write_text(
        "from flask import Flask, jsonify\n"
        "app = Flask(__name__)\n"
        "@app.route('/get_incidents')\n"
        "def get_incidents():\n"
        "    return jsonify(events=[])\n"
        "@app.route('/search')\n"
        "def search():\n"
        "    return jsonify(results=[])\n",
        encoding="utf-8",
    )
    output = tmp_path / "map_x"
    spec = {
        "target_name": "map_x",
        "main_task": "Serve a local map application.",
        "supported_scenarios": ["Serve HTTP API/web requests."],
        "routes": [
            {"route": "/", "function": "index", "methods": []},
            {"route": "/search", "function": "search", "methods": []},
            {"route": "/get_incidents", "function": "get_incidents", "methods": []},
        ],
    }

    scaffold = write_rebuild_scaffold(output_dir=output, spec=spec, force=False)
    comparison = compare_rebuild(
        source_dir=source,
        output_dir=output,
        spec=spec,
        analyzer_outputs={"project_map_report": {"summary": {"routes": 3}}},
    )

    assert scaffold["status"] == "written"
    assert (output / "app.py").exists()
    assert comparison["checks"]["preserves_flask_shape"] is True
    assert comparison["checks"]["preserves_bbox_capability"] is True
    assert comparison["checks"]["compiles"] is True
    assert "behavior_contracts_match" in comparison["checks"]


def test_api_rebuild_uses_behavior_blueprints(tmp_path: Path):
    source = tmp_path / "api"
    source.mkdir()
    (source / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok', 'version': '1'}\n",
        encoding="utf-8",
    )
    output = tmp_path / "api_x"
    spec = {
        "target_name": "api_x",
        "source_project": source.as_posix(),
        "main_task": "Serve an API.",
        "supported_scenarios": ["Serve API requests."],
        "routes": [{"route": "/health", "function": "health", "methods": ["GET"], "source": "app.py:health"}],
        "behavior_blueprints": [
            {"route": "/health", "method": "GET", "sample": {"status": "ok", "version": "1"}}
        ],
    }

    write_rebuild_scaffold(output_dir=output, spec=spec, force=False)
    comparison = compare_rebuild(
        source_dir=source,
        output_dir=output,
        spec=spec,
        analyzer_outputs={"project_map_report": {"summary": {"routes": 1}}},
    )

    assert "version" in (output / "app.py").read_text(encoding="utf-8")
    assert comparison["checks"]["behavior_contracts_match"] is True


def test_probe_env_readiness_reports_missing_modules(tmp_path: Path):
    project = tmp_path / "source"
    project.mkdir()
    (project / "requirements.txt").write_text("pydantic-settings\n", encoding="utf-8")
    behavior = {
        "cases": [
            {"source": {"status": "error", "reason": "ModuleNotFoundError: No module named 'pydantic_settings'"}}
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["status"] == "blocked"
    assert readiness["missing_modules"] == ["pydantic_settings"]
    assert readiness["install_candidates"][0]["package"] == "pydantic-settings"
    assert readiness["install_plan"]["allowed_packages"] == ["pydantic-settings"]
    assert readiness["policy"]["auto_install"] is False


def test_prepare_probe_env_requires_explicit_install(tmp_path: Path):
    readiness = {"install_plan": {"allowed_packages": ["pydantic-settings"], "blocked_packages": []}}

    result = prepare_probe_env(env_dir=tmp_path / "venv", readiness=readiness, allow_install=False)

    assert result["status"] == "planned"
    assert not (tmp_path / "venv").exists()


def test_programmer_verdict_distinguishes_executor_from_active_programmer():
    verdict = _verdict({"execution_score": 0.75, "coding_score": 0.0})

    assert verdict == "executor_only"

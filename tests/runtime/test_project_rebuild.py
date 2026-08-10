from __future__ import annotations

from pathlib import Path

from runtime.project_rebuild import (
    _pytest_project,
    build_project_rebuild_ir,
    build_rebuild_spec_from_ir,
    compare_rebuild,
    run_project_rebuild_trial,
    write_rebuild_scaffold,
)
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


def test_probe_env_readiness_handles_missing_parent_package(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    behavior = {
        "cases": [
            {
                "source": {"status": "error", "reason": "ModuleNotFoundError: No module named 'missing_parent.child'"},
                "target": {"status": "ok"},
            }
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert readiness["status"] == "blocked"
    assert readiness["missing_modules"] == ["missing_parent.child"]
    assert readiness["policy"]["auto_install"] is False


def test_probe_env_readiness_reads_pyproject_dependencies(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\n"
        "  \"shellingham>=1.5\",\n"
        "]\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'shellingham'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["declared"] is True
    assert readiness["install_candidates"][0]["risk"] == "low"
    assert readiness["install_plan"]["allowed_packages"] == ["shellingham"]


def test_probe_env_readiness_maps_declared_submodules_to_root_package(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\n"
        "  \"filelock>=3\",\n"
        "  \"urwid>=2\",\n"
        "  \"pyproject-hooks>=1\",\n"
        "]\n",
        encoding="utf-8",
    )
    behavior = {
        "cases": [
            {"source": {"status": "error", "reason": "No module named 'filelock.version'"}},
            {"source": {"status": "error", "reason": "No module named 'urwid.version'"}},
            {"source": {"status": "error", "reason": "No module named 'pyproject_hooks'"}},
        ]
    }

    readiness = probe_env_readiness(project, behavior)

    assert [row["package"] for row in readiness["install_candidates"]] == [
        "filelock",
        "urwid",
        "pyproject-hooks",
    ]
    assert all(row["risk"] == "low" for row in readiness["install_candidates"])
    assert readiness["install_plan"]["blocked_packages"] == []
    assert readiness["install_plan"]["allowed_packages"] == ["filelock", "pyproject-hooks", "urwid"]


def test_probe_env_readiness_treats_declared_underscore_package_as_low_risk(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        "dependencies = [\"pyproject_hooks\"]\n",
        encoding="utf-8",
    )
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'pyproject_hooks'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["risk"] == "low"
    assert readiness["install_plan"]["allowed_packages"] == ["pyproject_hooks"]


def test_probe_env_readiness_blocks_declared_native_dependencies(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements.txt").write_text("pycurl\n", encoding="utf-8")
    behavior = {"cases": [{"source": {"status": "error", "reason": "No module named 'pycurl'"}}]}

    readiness = probe_env_readiness(project, behavior)

    assert readiness["install_candidates"][0]["package"] == "pycurl"
    assert readiness["install_candidates"][0]["risk"] == "native"
    assert readiness["install_plan"]["allowed_packages"] == []
    assert readiness["install_plan"]["native_packages"] == ["pycurl"]


def test_behavior_depth_classifies_source_unavailable_reasons(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "pkg.py").write_text("raise SystemError('The installed pydantic-core version is incompatible')\n", encoding="utf-8")
    (target / "pkg.py").write_text("VALUE = 1\n", encoding="utf-8")

    comparison = compare_rebuild(
        source_dir=source,
        output_dir=target,
        spec={"target_name": "target", "entrypoints": ["pkg.py"], "core_capabilities": ["pkg.py"]},
        analyzer_outputs={"project_map_report": {"summary": {"routes": 0}}},
    )

    reasons = comparison["behavior"]["depth"]["source_unavailable_reasons"]
    assert reasons["runtime_version_mismatch"] == 1


def test_prepare_probe_env_requires_explicit_install(tmp_path: Path):
    readiness = {
        "install_plan": {
            "allowed_packages": ["pydantic-settings"],
            "blocked_packages": [],
            "native_packages": ["pyyaml"],
        }
    }

    result = prepare_probe_env(env_dir=tmp_path / "venv", readiness=readiness, allow_install=False)

    assert result["status"] == "planned"
    assert result["native_packages"] == ["pyyaml"]
    assert not (tmp_path / "venv").exists()


def test_programmer_verdict_distinguishes_executor_from_active_programmer():
    verdict = _verdict({"execution_score": 0.75, "coding_score": 0.0})

    assert verdict == "executor_only"


def test_rebuild_spec_is_compiled_from_system_knowledge_ir(tmp_path: Path):
    source = tmp_path / "api"
    source.mkdir()
    (source / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )
    analyzer_outputs = {
        "project_map_report": {
            "artifact_type": "ProjectMapReport",
            "project": source.as_posix(),
            "summary": {"name": "api", "frameworks": ["FastAPI"], "entrypoints": ["app.py"]},
            "answers": {"1_scope": {"main_task": "Serve health API."}},
        },
        "extract_python_structure": {
            "routes": [
                {
                    "path": "app.py",
                    "route": "/health",
                    "function": "health",
                    "methods": ["GET"],
                }
            ]
        },
    }

    ir = build_project_rebuild_ir(source_dir=source, analyzer_outputs=analyzer_outputs)
    spec = build_rebuild_spec_from_ir(source_dir=source, ir=ir)

    assert ir["artifact_type"] == "SystemKnowledgeIR"
    assert ir["origin"] == "source_project"
    assert spec["source_ir_schema"] == "system_knowledge_ir.v0"
    assert spec["quality_targets"]["compiled_from_system_knowledge_ir"] is True
    assert spec["knowledge_ir_snapshot"]["artifact_type"] == "SystemKnowledgeIR"
    assert spec["routes"][0]["route"] == "/health"
    assert spec["behavior_blueprints"][0]["sample"] == {"status": "ok"}


def test_project_rebuild_trial_reports_round_trip_ir(tmp_path: Path):
    source = tmp_path / "api"
    source.mkdir()
    (source / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )

    report = run_project_rebuild_trial(
        root=tmp_path,
        source_dir=source,
        output_dir=tmp_path / "api_x",
        force=True,
    )

    assert report["knowledge_ir"]["artifact_type"] == "SystemKnowledgeIR"
    assert report["round_trip"]["artifact_type"] == "ProjectRebuildRoundTripReport"
    assert "diff" in report["round_trip"]
    assert "improvement_backlog" in report["round_trip"]
    assert "backlog_summary" in report["round_trip"]
    assert report["spec"]["quality_targets"]["compiled_from_system_knowledge_ir"] is True
    assert (tmp_path / "api_x" / ".cognitive_os" / "system_knowledge_ir.json").exists()


def test_generated_project_pytest_disables_external_plugin_autoload(tmp_path: Path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("runtime.project_rebuild.subprocess.run", fake_run)

    assert _pytest_project(tmp_path) is True
    assert calls[0][1]["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"


def test_round_trip_reads_embedded_system_knowledge_ir(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "README.md").write_text("Async library for worker queues.\n", encoding="utf-8")
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text("def run_worker():\n    return 'ok'\n", encoding="utf-8")

    report = run_project_rebuild_trial(
        root=tmp_path,
        source_dir=source,
        output_dir=tmp_path / "library_x",
        force=True,
    )

    diff = report["round_trip"]["diff"]

    assert report["round_trip"]["target_ir"]["origin"] == "source_project_embedded_ir"
    assert report["round_trip"]["code_recovery_target_ir"]["origin"] != "source_project_embedded_ir"
    assert not [loss for loss in diff["losses"] if loss["category"] == "purpose"]
    assert not [loss for loss in diff["losses"] if loss["category"] == "public_interfaces"]
    assert report["round_trip"]["code_recovery_status"] == "ok"
    code_losses = report["round_trip"]["code_recovery_diff"]["losses"]
    assert not [loss for loss in code_losses if loss["category"] == "public_interfaces"]
    assert not [loss for loss in code_losses if loss["category"] == "purpose"]
    assert (tmp_path / "library_x" / "pkg" / "__init__.py").exists()


def test_library_rebuild_uses_module_import_blueprints(tmp_path: Path):
    source = tmp_path / "library"
    source.mkdir()
    (source / "README.md").write_text("Reusable greeting helpers.\n", encoding="utf-8")
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "__all__ = ['greet']\n"
        "def greet():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    report = run_project_rebuild_trial(
        root=tmp_path,
        source_dir=source,
        output_dir=tmp_path / "library_x",
        force=True,
    )

    blueprints = report["spec"]["behavior_blueprints"]
    module_blueprints = [row for row in blueprints if row.get("kind") == "module_import"]
    module_cases = [row for row in report["comparison"]["behavior"]["cases"] if row["probe"]["kind"] == "module_import"]

    assert module_blueprints
    assert module_blueprints[0]["shape"]["public_names"] == ["greet"]
    assert module_cases
    assert module_cases[0]["passed"] is True

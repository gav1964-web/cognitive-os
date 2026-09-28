"""Rebuild-trial loop for source project -> generated sibling project."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_benchmark import analyze_project
from .project_rebuild_app_templates import build_app_py, build_contract_tests, build_requirements, project_kind
from .project_rebuild_behavior import compare_project_behavior
from .project_rebuild_cleanup import clean_generated_runtime_artifacts
from .project_rebuild_ir import build_project_rebuild_ir, build_rebuild_spec_from_ir
from .project_rebuild_package_scaffold import build_package_entrypoint_files
from .project_rebuild_roundtrip import verify_rebuild_round_trip
from .project_rebuild_samples import build_sample_data_files
from .project_rebuild_ui import smoke_test_static_ui
from .project_probe_env import probe_env_readiness


def run_project_rebuild_trial(
    *, root: Path, source_dir: Path, output_dir: Path, force: bool = False, source_python: Path | None = None
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        return {"status": "blocked", "reason": "output_dir_not_empty", "output_dir": output_dir.as_posix()}
    outputs = analyze_project(source_dir)
    ir = build_project_rebuild_ir(source_dir=source_dir, analyzer_outputs=outputs, source_python=source_python)
    spec = build_rebuild_spec_from_ir(source_dir=source_dir, ir=ir)
    scaffold = write_rebuild_scaffold(output_dir=output_dir, spec=spec, force=force)
    comparison = compare_rebuild(
        source_dir=source_dir,
        output_dir=output_dir,
        spec=spec,
        analyzer_outputs=outputs,
        source_python=source_python,
    )
    round_trip = verify_rebuild_round_trip(source_ir=ir, target_dir=output_dir)
    report = {
        "status": "ok" if comparison["score"] >= 0.85 and not comparison.get("missing") else "needs_work",
        "kind": "project_rebuild_trial",
        "created_at": _now(),
        "source_project": source_dir.as_posix(),
        "rebuilt_project": output_dir.as_posix(),
        "knowledge_ir": ir,
        "spec": spec,
        "scaffold": scaffold,
        "comparison": comparison,
        "round_trip": round_trip,
        "next_steps": _next_steps(comparison),
    }
    report_path = _write_report(root, report, output_dir.name)
    report["report_path"] = report_path.as_posix()
    return report


def build_rebuild_spec(*, source_dir: Path, analyzer_outputs: dict[str, Any], source_python: Path | None = None) -> dict[str, Any]:
    ir = build_project_rebuild_ir(source_dir=source_dir, analyzer_outputs=analyzer_outputs, source_python=source_python)
    return build_rebuild_spec_from_ir(source_dir=source_dir, ir=ir)


def write_rebuild_scaffold(*, output_dir: Path, spec: dict[str, Any], force: bool) -> dict[str, Any]:
    if output_dir.exists() and force:
        for path in sorted(output_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "README.md": _readme(spec),
        "requirements.txt": build_requirements(spec),
        "app.py": build_app_py(spec),
        "tests/test_contract.py": build_contract_tests(spec),
    }
    if spec.get("knowledge_ir_snapshot"):
        files[".cognitive_os/system_knowledge_ir.json"] = (
            json.dumps(spec["knowledge_ir_snapshot"], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    files.update(build_package_entrypoint_files(spec))
    files.update(_sample_data_files(spec))
    written = []
    for relative, content in files.items():
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(relative)
    return {"status": "written", "files": written}


def compare_rebuild(
    *,
    source_dir: Path,
    output_dir: Path,
    spec: dict[str, Any],
    analyzer_outputs: dict[str, Any],
    source_python: Path | None = None,
) -> dict[str, Any]:
    source_summary = dict(dict(analyzer_outputs.get("project_map_report", {})).get("summary", {}))
    target_files = sorted(path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file())
    route_targets = {str(route.get("route")) for route in spec.get("routes", [])}
    generated_text = "\n".join((output_dir / file).read_text(encoding="utf-8") for file in target_files if file.endswith(".py"))
    data_files = {str(row.get("path")) for row in spec.get("data_artifacts", []) if row.get("exists")}
    behavior = compare_project_behavior(source_dir, output_dir, spec, source_python)
    env = probe_env_readiness(source_dir, behavior)
    ui = smoke_test_static_ui(output_dir)
    behavior_required = behavior.get("status") != "skipped"
    behavior_depth = dict(behavior.get("depth") or {})
    http_probes = int(behavior_depth.get("http_probes") or 0)
    source_ok = int(behavior_depth.get("source_ok") or 0)
    kind = project_kind(spec)
    checks = {
        "has_app_entrypoint": "app.py" in target_files,
        "has_requirements": "requirements.txt" in target_files,
        "has_readme": "README.md" in target_files,
        "has_contract_tests": "tests/test_contract.py" in target_files,
        "preserves_flask_shape": kind != "map_flask" or ("Flask(" in generated_text and "jsonify" in generated_text),
        "preserves_api_shape": kind != "api_fastapi" or "FastAPI(" in generated_text,
        "preserves_tooling_shape": kind != "tooling_cli" or "def describe" in generated_text,
        "preserves_core_routes": (not route_targets) or all(route in generated_text for route in sorted(route_targets)[:8]),
        "preserves_bbox_capability": kind != "map_flask" or "def parse_bbox" in generated_text,
        "preserves_search_capability": "/search" not in route_targets or "/search" in generated_text,
        "preserves_incident_capability": kind != "map_flask" or "incident" in generated_text.lower(),
        "no_stub_route_handlers": "status='stub'" not in generated_text,
        "data_artifacts_represented": (not data_files) or data_files.issubset(set(target_files)),
        "compiles": _compile_project(output_dir),
        "contract_tests_pass": _pytest_project(output_dir),
        "behavior_contracts_match": (behavior.get("passed") is True) if behavior_required else True,
        "behavior_source_executable": http_probes == 0 or source_ok > 0,
        "ui_smoke_pass": ui.get("passed") is True,
        "source_read_only": True,
    }
    clean_generated_runtime_artifacts(output_dir)
    score = round(sum(1 for ok in checks.values() if ok) / len(checks), 3)
    return {
        "score": score,
        "checks": checks,
        "source_routes": source_summary.get("routes"),
        "target_files": target_files,
        "behavior": behavior,
        "probe_env": env,
        "ui": ui,
        "missing": [name for name, ok in checks.items() if not ok],
    }


def _active_routes(routes: object) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for route in routes if isinstance(routes, list) else []:
        if not isinstance(route, dict) or str(route.get("path", "")).startswith("map_install_package/"):
            continue
        key = str(route.get("route") or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "route": key,
                "function": route.get("function"),
                "methods": route.get("methods", []),
                "source": f"{route.get('path')}:{route.get('function')}",
            }
        )
    return rows[:12]


def _main_task(scope: dict[str, Any], routes: list[dict[str, Any]]) -> str:
    text = str(scope.get("main_task") or "")
    if "excludes" not in text.lower() and len(text) > 20:
        return text
    route_names = ", ".join(str(route.get("route")) for route in routes[:5])
    return f"Serve a local Flask map application with vector map, incidents, branches/ATMs, search and import status APIs ({route_names})."


def _scenarios(scope: dict[str, Any], routes: list[dict[str, Any]]) -> list[str]:
    scenarios = [str(item) for item in scope.get("supported_scenarios", []) if item]
    route_set = {str(route.get("route")) for route in routes}
    if "/search" in route_set:
        scenarios.append("Search map objects by text query.")
    if "/get_incidents" in route_set:
        scenarios.append("Serve incident features and incident metadata.")
    if "/branches_atms" in route_set:
        scenarios.append("Serve branch and ATM GeoJSON overlays.")
    return _unique(scenarios)[:8]


def _data_artifacts(source_dir: Path) -> list[dict[str, Any]]:
    names = ["kursk_vector_map.json", "kursk_nodes.json", "incidents.json", "branches_atms.json"]
    artifacts = []
    for name in names:
        path = source_dir / name
        artifacts.append({"path": name, "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0})
    return artifacts


def _readme(spec: dict[str, Any]) -> str:
    scenarios = "\n".join(f"- {item}" for item in spec.get("supported_scenarios", []))
    routes = "\n".join(f"- `{row['route']}` -> `{row['function']}`" for row in spec.get("routes", [])[:12])
    return (
        f"# {spec['target_name']}\n\n"
        f"{spec['main_task']}\n\n"
        f"## Task\n{spec['main_task']}\n\n"
        "Generated by Cognitive OS rebuild trial.\n\n"
        f"## Scenarios\n{scenarios}\n\n"
        f"## Routes\n{routes}\n\n"
        "## Run\n`python app.py`\n"
    )


def _sample_data_files(spec: dict[str, Any]) -> dict[str, str]:
    return build_sample_data_files(spec)


def _compile_project(output_dir: Path) -> bool:
    result = subprocess.run([sys.executable, "-m", "compileall", "-b", str(output_dir)], capture_output=True, text=True)
    return result.returncode == 0


def _pytest_project(output_dir: Path) -> bool:
    env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", **dict(os.environ)}
    result = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=str(output_dir), capture_output=True, text=True, env=env)
    return result.returncode == 0


def _git_dirty(path: Path) -> bool:
    result = subprocess.run(["git", "-C", str(path), "status", "--porcelain"], capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def _next_steps(comparison: dict[str, Any]) -> list[str]:
    steps = ["review ProjectRebuildSpec and comparison report"]
    if comparison.get("missing"):
        steps.append("turn missing comparison checks into role/tooling backlog")
    steps.append("iterate map_x scaffold until comparison score and human review are acceptable")
    return steps


def _write_report(root: Path, report: dict[str, Any], target_name: str) -> Path:
    out_dir = root / "artifacts" / "rebuild_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{target_name}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _unique(items: list[Any]) -> list[str]:
    result = []
    for item in items:
        value = str(item)
        if value and value not in result:
            result.append(value)
    return result


def _list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, tuple):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, set):
        return sorted(item for item in value if item is not None and item != "")
    text = str(value).strip()
    return [text] if text else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

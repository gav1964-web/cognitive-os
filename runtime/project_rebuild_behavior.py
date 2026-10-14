"""Generic behavioral probes for rebuild trials."""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .behavior_probe_depth import behavior_cases_depth
from .project_http_probe import open_http_probe, response_shape_compatible
from .project_module_probe import module_shape_compatible, open_module_import


def compare_project_behavior(source_dir: Path, target_dir: Path, spec: dict[str, Any], source_python: Path | None = None) -> dict[str, Any]:
    plan = _probe_plan(spec)
    cases = []
    for probe in plan:
        if probe["kind"] == "http":
            cases.append(_compare_http_probe(source_dir, target_dir, probe, source_python))
        elif probe["kind"] == "module_import":
            cases.append(_compare_module_import_probe(source_dir, target_dir, probe, source_python))
        elif probe["kind"] == "capability_manifest":
            cases.append(_compare_capability_probe(source_dir, target_dir, probe))
    if not cases:
        return {"status": "skipped", "reason": "no behavioral probes", "passed": True, "cases": [], "plan": plan}
    depth = behavior_cases_depth(cases)
    return {
        "status": "ok",
        "passed": all(case["passed"] for case in cases),
        "cases": cases,
        "depth": depth,
        "plan": plan,
        "summary": {
            "total": len(cases),
            "passed": sum(1 for case in cases if case["passed"]),
            "failed": sum(1 for case in cases if not case["passed"]),
        },
    }


def collect_source_response_blueprints(source_dir: Path, spec: dict[str, Any], source_python: Path | None = None) -> list[dict[str, Any]]:
    blueprints = []
    for probe in _probe_plan(spec):
        if probe["kind"] != "http":
            continue
        result = open_http_probe(source_dir, probe, source_python)
        response = result.get("response", {})
        if result.get("status") == "ok" and response.get("is_json"):
            blueprints.append(
                {
                    "route": probe["route"],
                    "method": probe["method"],
                    "path": probe["path"],
                    "status_code": response.get("status_code"),
                    "json_kind": response.get("json_kind"),
                    "json_keys": response.get("json_keys", []),
                    "sample": response.get("sample"),
                }
            )
    for probe in _probe_plan(spec):
        if probe["kind"] != "module_import":
            continue
        result = open_module_import(source_dir, probe, source_python)
        if result.get("status") == "ok":
            blueprints.append(
                {
                    "kind": "module_import",
                    "path": probe["path"],
                    "module": result.get("module"),
                    "shape": result.get("shape", {}),
                }
            )
    return blueprints


def _probe_plan(spec: dict[str, Any]) -> list[dict[str, Any]]:
    probes = []
    for row in spec.get("routes", [])[:8]:
        methods = [str(item).upper() for item in row.get("methods", [])] or ["GET"]
        if "GET" not in methods:
            continue
        route = str(row.get("route") or "")
        probes.append({"kind": "http", "method": "GET", "path": _sample_path(route), "route": route, "source": row.get("source")})
    if not probes and spec.get("core_capabilities"):
        for entrypoint in _module_entrypoints(spec):
            probes.append({"kind": "module_import", "path": entrypoint})
    if not probes and spec.get("core_capabilities"):
        probes.append({"kind": "capability_manifest", "expected": [str(item) for item in spec["core_capabilities"][:8]]})
    return probes


def _module_entrypoints(spec: dict[str, Any]) -> list[str]:
    result = []
    for value in spec.get("entrypoints", [])[:12]:
        path = str(value or "").replace("\\", "/")
        if path.endswith(".py") and not path.endswith("/__main__.py") and path != "app.py":
            result.append(path)
    return result[:5]


def _compare_http_probe(source_dir: Path, target_dir: Path, probe: dict[str, Any], source_python: Path | None) -> dict[str, Any]:
    source = open_http_probe(source_dir, probe, source_python)
    target = open_http_probe(target_dir, probe)
    checks = {
        "target_runnable": target["status"] == "ok",
        "target_success": target.get("response", {}).get("status_code", 500) < 500,
        "source_available_or_target_stable": source["status"] == "ok" or target["status"] == "ok",
        "status_code_match_when_source_available": source["status"] != "ok"
        or source["response"]["status_code"] == target.get("response", {}).get("status_code"),
        "shape_compatible_when_source_available": source["status"] != "ok"
        or response_shape_compatible(source["response"], target.get("response", {})),
    }
    return {"probe": probe, "passed": all(checks.values()), "checks": checks, "source": source, "target": target}


def _compare_module_import_probe(source_dir: Path, target_dir: Path, probe: dict[str, Any], source_python: Path | None) -> dict[str, Any]:
    source = open_module_import(source_dir, probe, source_python)
    target = open_module_import(target_dir, probe)
    checks = {
        "target_importable": target["status"] == "ok",
        "source_available_or_target_importable": source["status"] == "ok" or target["status"] == "ok",
        "public_shape_compatible_when_source_available": source["status"] != "ok"
        or module_shape_compatible(source.get("shape", {}), target.get("shape", {})),
    }
    return {"probe": probe, "passed": all(checks.values()), "checks": checks, "source": source, "target": target}


def _compare_capability_probe(source_dir: Path, target_dir: Path, probe: dict[str, Any]) -> dict[str, Any]:
    target = _call_describe(target_dir / "app.py")
    expected = set(probe.get("expected", []))
    actual = set(target.get("capabilities", []))
    checks = {
        "target_describable": target.get("status") == "available",
        "capabilities_preserved": expected.issubset(actual),
    }
    return {
        "probe": probe,
        "passed": all(checks.values()),
        "checks": checks,
        "source": {"status": "not_executed", "reason": "manifest probe uses spec evidence"},
        "target": target,
    }


def _sample_path(route: str) -> str:
    if route == "/get_vector_map":
        return "/get_vector_map?bbox=34,50,35,51&zoom=8"
    if route == "/search":
        return "/search?q=sample"
    if "<language:str>/<path:path>" in route:
        return "/en/index.html"
    if "<language:str>" in route:
        return "/en"
    return route or "/"


def _call_describe(path: Path) -> dict[str, Any]:
    try:
        module = _load_module(path, f"rebuild_manifest_{abs(hash(path))}", path.parent)
        result = module.describe()
        return {"status": result.get("status"), "capabilities": result.get("capabilities", [])}
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "capabilities": []}


def _load_module(path: Path, name: str, root: Path) -> Any:
    with _path_front(root, path.parent):
        previous = sys.modules.pop(name, None)
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"cannot load module from {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            if previous is not None:
                sys.modules[name] = previous


@contextmanager
def _path_front(*paths: Path):
    added = []
    for path in reversed(paths):
        value = str(path)
        sys.path.insert(0, value)
        added.append(value)
    try:
        yield
    finally:
        for value in added:
            try:
                sys.path.remove(value)
            except ValueError:
                pass

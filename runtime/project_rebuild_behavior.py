"""Generic behavioral probes for rebuild trials."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def compare_project_behavior(source_dir: Path, target_dir: Path, spec: dict[str, Any], source_python: Path | None = None) -> dict[str, Any]:
    plan = _probe_plan(spec)
    cases = []
    for probe in plan:
        if probe["kind"] == "http":
            cases.append(_compare_http_probe(source_dir, target_dir, probe, source_python))
        elif probe["kind"] == "capability_manifest":
            cases.append(_compare_capability_probe(source_dir, target_dir, probe))
    if not cases:
        return {"status": "skipped", "reason": "no behavioral probes", "passed": True, "cases": [], "plan": plan}
    depth = _behavior_depth(cases)
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
        result = _open_http(source_dir, probe, source_python)
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
        probes.append({"kind": "capability_manifest", "expected": [str(item) for item in spec["core_capabilities"][:8]]})
    return probes


def _compare_http_probe(source_dir: Path, target_dir: Path, probe: dict[str, Any], source_python: Path | None) -> dict[str, Any]:
    source = _open_http(source_dir, probe, source_python)
    target = _open_http(target_dir, probe)
    checks = {
        "target_runnable": target["status"] == "ok",
        "target_success": target.get("response", {}).get("status_code", 500) < 500,
        "source_available_or_target_stable": source["status"] == "ok" or target["status"] == "ok",
        "status_code_match_when_source_available": source["status"] != "ok"
        or source["response"]["status_code"] == target.get("response", {}).get("status_code"),
        "shape_compatible_when_source_available": source["status"] != "ok"
        or _shape_compatible(source["response"], target.get("response", {})),
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


def _behavior_depth(cases: list[dict[str, Any]]) -> dict[str, int]:
    depth = {"http_probes": 0, "manifest_probes": 0, "source_ok": 0, "source_unavailable": 0}
    for case in cases:
        probe = dict(case.get("probe") or {})
        source = dict(case.get("source") or {})
        if probe.get("kind") == "http":
            depth["http_probes"] += 1
            if source.get("status") == "ok":
                depth["source_ok"] += 1
            else:
                depth["source_unavailable"] += 1
        elif probe.get("kind") == "capability_manifest":
            depth["manifest_probes"] += 1
    return depth


def _open_http(project_dir: Path, probe: dict[str, Any], python_executable: Path | None = None) -> dict[str, Any]:
    app_path = _find_app_path(project_dir, probe)
    if app_path is None:
        return {"status": "skipped", "reason": "no importable app path"}
    if python_executable is not None:
        return _open_http_subprocess(project_dir, app_path, probe, python_executable)
    try:
        module = _load_module(app_path, f"rebuild_probe_{abs(hash(app_path))}", project_dir)
        client = _http_client(module)
        if client is None:
            return {"status": "skipped", "reason": "no supported app adapter", "app_path": app_path.as_posix()}
        response = client(probe["method"], probe["path"])
        return {"status": "ok", "app_path": app_path.as_posix(), "response": _response_shape(response)}
    except Exception as exc:  # pragma: no cover - defensive report path
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "app_path": app_path.as_posix()}


def _open_http_subprocess(project_dir: Path, app_path: Path, probe: dict[str, Any], python_executable: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([repo_root.as_posix(), project_dir.as_posix(), env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [
            str(python_executable),
            "-m",
            "runtime.project_probe_runner",
            "--app-path",
            app_path.as_posix(),
            "--project-root",
            project_dir.as_posix(),
            "--method",
            str(probe["method"]),
            "--path",
            str(probe["path"]),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        return {"status": "error", "reason": result.stderr[-1000:] or "probe subprocess failed", "app_path": app_path.as_posix()}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": result.stdout[-1000:], "app_path": app_path.as_posix()}
    payload["app_path"] = app_path.as_posix()
    payload["python"] = python_executable.as_posix()
    return payload


def _find_app_path(project_dir: Path, probe: dict[str, Any]) -> Path | None:
    source = str(probe.get("source") or "")
    if source:
        path = project_dir / source.split(":", 1)[0]
        if path.exists():
            return path
    for candidate in [project_dir / "app.py", project_dir / "app" / "api" / "server.py"]:
        if candidate.exists():
            return candidate
    return None


def _http_client(module: Any):
    app = getattr(module, "app", None)
    if app is None:
        return None
    if hasattr(app, "test_client"):
        client = app.test_client()
        return lambda method, path: client.open(path=path, method=method)
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        return lambda method, path: client.request(method, path)
    except Exception:
        return None


def _response_shape(response: Any) -> dict[str, Any]:
    payload = _payload(response)
    return {
        "status_code": int(response.status_code),
        "is_json": payload is not None,
        "json_kind": _json_kind(payload),
        "json_keys": sorted(str(key) for key in payload.keys())[:20] if isinstance(payload, dict) else [],
        "shape": _shape(payload),
        "sample": _thin_payload(payload),
        "bytes": len(response.content if hasattr(response, "content") else response.get_data()),
    }


def _payload(response: Any) -> Any:
    try:
        return response.get_json(silent=True)
    except Exception:
        try:
            return response.json()
        except Exception:
            return None


def _shape_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
    if source.get("json_kind") != target.get("json_kind"):
        return False
    if not _keys_preserved(source, target):
        return False
    return _field_types_compatible(source, target)


def _keys_preserved(source: dict[str, Any], target: dict[str, Any]) -> bool:
    keys = set(source.get("json_keys", []))
    if not keys or source.get("json_kind") != "object" or target.get("json_kind") != "object":
        return True
    return keys.issubset(set(target.get("json_keys", [])))


def _field_types_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
    source_types = dict(dict(source.get("shape") or {}).get("field_types") or {})
    target_types = dict(dict(target.get("shape") or {}).get("field_types") or {})
    common = set(source_types).intersection(target_types)
    return not common or all(source_types[key] == target_types[key] for key in common)


def _shape(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features")
        first = features[0] if isinstance(features, list) and features else None
        return {"kind": "feature_collection", "length": len(features) if isinstance(features, list) else None, "field_types": _field_types(first)}
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {"kind": "array", "length": len(payload), "field_types": _field_types(first)}
    if isinstance(payload, dict):
        return {"kind": "object", "field_types": _field_types(payload)}
    return {"kind": _json_kind(payload)}


def _field_types(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _json_kind(item) for key, item in sorted(value.items())[:20]}


def _thin_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_thin_payload(item) for item in payload[:5]]
    if isinstance(payload, dict):
        result = {}
        for key, value in list(payload.items())[:20]:
            result[str(key)] = _thin_payload(value)
        return result
    if isinstance(payload, (str, int, float, bool)) or payload is None:
        return payload
    return str(payload)


def _json_kind(payload: Any) -> str:
    if isinstance(payload, dict):
        return "object"
    if isinstance(payload, list):
        return "array"
    if payload is None:
        return "none"
    return type(payload).__name__


def _sample_path(route: str) -> str:
    if route == "/get_vector_map":
        return "/get_vector_map?bbox=34,50,35,51&zoom=8"
    if route == "/search":
        return "/search?q=sample"
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

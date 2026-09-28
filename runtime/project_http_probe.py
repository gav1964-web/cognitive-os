"""HTTP behavior probe loading and response-shape helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .executable_acceptance_policy import dependency_stub_policy
from .project_http_static_probe import static_http_route_probe
from .project_module_probe_stubs import _can_stub_missing, _install_stub_module, _plugin_loader_retry_module


def open_http_probe(project_dir: Path, probe: dict[str, Any], python_executable: Path | None = None) -> dict[str, Any]:
    app_path = _find_app_path(project_dir, probe)
    if app_path is None:
        return {"status": "skipped", "reason": "no importable app path"}
    if python_executable is not None:
        return _open_http_subprocess(project_dir, app_path, probe, python_executable)
    loaded: dict[str, Any] = {"dependency_stubs": []}
    try:
        loaded = _load_module_with_stubs(app_path, f"rebuild_probe_{abs(hash(app_path))}", project_dir)
        client = _http_client(loaded["module"], _factory_root(project_dir, app_path))
        if client is None:
            fallback = static_http_route_probe(app_path, probe)
            if fallback.get("status") == "ok":
                fallback["dependency_stubs"] = list(loaded["dependency_stubs"]) + list(fallback.get("dependency_stubs") or [])
                return fallback
            return {"status": "skipped", "reason": "no supported app adapter", "app_path": app_path.as_posix()}
        try:
            response = client(probe["method"], probe["path"])
        except Exception:
            fallback = static_http_route_probe(app_path, probe)
            if fallback.get("status") == "ok":
                fallback["dependency_stubs"] = list(loaded["dependency_stubs"]) + list(fallback.get("dependency_stubs") or [])
                return fallback
            raise
        return {
            "status": "ok",
            "app_path": app_path.as_posix(),
            "response": _response_shape(response),
            "dependency_stubs": loaded["dependency_stubs"],
        }
    except Exception as exc:  # pragma: no cover - defensive report path
        fallback = static_http_route_probe(app_path, probe)
        if fallback.get("status") == "ok":
            dependency_stubs = list(loaded.get("dependency_stubs") or []) + list(getattr(exc, "dependency_stubs", []) or [])
            fallback["dependency_stubs"] = dependency_stubs + list(fallback.get("dependency_stubs") or [])
            fallback["fallback_reason"] = f"{type(exc).__name__}: {exc}"
            _remove_named_modules(dependency_stubs)
            return fallback
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "app_path": app_path.as_posix()}
    finally:
        _remove_named_modules(list(loaded.get("dependency_stubs") or []))


def response_shape_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
    if source.get("json_kind") != target.get("json_kind"):
        return False
    if not _keys_preserved(source, target):
        return False
    return _field_types_compatible(source, target)


def _open_http_subprocess(project_dir: Path, app_path: Path, probe: dict[str, Any], python_executable: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    roots = [path.as_posix() for path in _import_roots(project_dir, app_path)]
    env["PYTHONPATH"] = os.pathsep.join([repo_root.as_posix(), *roots, env.get("PYTHONPATH", "")])
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
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
        payload = _load_probe_payload(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": result.stdout[-1000:], "app_path": app_path.as_posix()}
    payload["app_path"] = app_path.as_posix()
    payload["python"] = python_executable.as_posix()
    if payload.get("status") != "ok":
        fallback = static_http_route_probe(app_path, probe)
        if fallback.get("status") == "ok":
            fallback["dependency_stubs"] = list(payload.get("dependency_stubs") or []) + list(fallback.get("dependency_stubs") or [])
            fallback["fallback_reason"] = str(payload.get("reason") or payload.get("status") or "subprocess source unavailable")
            fallback["python"] = python_executable.as_posix()
            return fallback
    return payload


def _load_probe_payload(stdout: str) -> dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            if line.strip().startswith("{"):
                payload = json.loads(line)
                if isinstance(payload, dict):
                    return payload
        raise


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


def _http_client(module: Any, factory_root: Path | None = None):
    app = getattr(module, "app", None)
    if app is None and callable(getattr(module, "create_app", None)):
        app = _call_app_factory(module.create_app, factory_root)
    if app is None:
        return None
    if hasattr(app, "asgi_client"):
        client = app.asgi_client
        return lambda method, path: _normalize_response(_run_maybe_awaitable(client.request(method, path)))
    if hasattr(app, "test_client"):
        client_factory = app.test_client
        client = client_factory() if callable(client_factory) else client_factory
        return lambda method, path: _normalize_response(_request_with_client(client, method, path))
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        return lambda method, path: client.request(method, path, follow_redirects=False)
    except Exception:
        return None


def _request_with_client(client: Any, method: str, path: str) -> Any:
    if hasattr(client, "open"):
        return client.open(path=path, method=method)
    method_handler = getattr(client, method.lower(), None)
    if callable(method_handler):
        return method_handler(path)
    if hasattr(client, "request"):
        return client.request(method, path)
    raise TypeError(f"unsupported test client: {type(client).__name__}")


def _normalize_response(response: Any) -> Any:
    if isinstance(response, tuple) and response:
        return response[-1]
    return response


def _run_maybe_awaitable(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _call_app_factory(factory: Any, factory_root: Path | None) -> Any:
    for args in ((factory_root,), ()):
        try:
            return factory(*[arg for arg in args if arg is not None])
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _factory_root(project_dir: Path, app_path: Path) -> Path:
    try:
        relative = app_path.relative_to(project_dir)
    except ValueError:
        return app_path.parent
    return project_dir / relative.parts[0] if len(relative.parts) > 1 else project_dir


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
        return {str(key): _thin_payload(value) for key, value in list(payload.items())[:20]}
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


def _load_module(path: Path, name: str, root: Path) -> Any:
    with _path_front(*_import_roots(root, path)):
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


def _import_roots(root: Path, path: Path) -> list[Path]:
    roots = [root]
    try:
        relative = path.parent.relative_to(root)
    except ValueError:
        return [root, path.parent]
    current = root
    for part in relative.parts:
        current = current / part
        roots.append(current)
    roots.append(path.parent)
    return list(dict.fromkeys(roots))


def _load_module_with_stubs(path: Path, name: str, root: Path) -> dict[str, Any]:
    policy = dependency_stub_policy()
    stubbed: list[str] = []
    max_missing = int(policy.get("max_missing_modules") or 0)
    while True:
        try:
            return {"module": _load_module(path, name, root), "dependency_stubs": stubbed}
        except ModuleNotFoundError as exc:
            missing = str(getattr(exc, "name", "") or "")
            if not _can_stub_missing(root, missing, policy, stubbed, max_missing):
                raise
            _remove_modules_under(root)
            _install_stub_module(missing)
            stubbed.append(missing)
        except Exception as exc:
            retry = _plugin_loader_retry_module(root, policy, stubbed, exc)
            if not retry:
                setattr(exc, "dependency_stubs", list(stubbed))
                raise
            _remove_modules_under(root)
            _remove_named_modules([retry])
            _install_stub_module(retry)
            stubbed.append(retry)


def _remove_modules_under(root: Path) -> None:
    resolved = root.resolve()
    for name, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            Path(str(module_file)).resolve().relative_to(resolved)
        except ValueError:
            continue
        sys.modules.pop(name, None)


def _remove_named_modules(names: list[str]) -> None:
    for name in reversed(names):
        root = name.split(".", 1)[0]
        for module_name in [item for item in list(sys.modules) if item == root or item.startswith(f"{root}.")]:
            sys.modules.pop(module_name, None)


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

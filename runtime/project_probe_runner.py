"""Subprocess HTTP probe runner used by prepared probe environments."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import inspect
import importlib.util
import json
import sys
import traceback
import types
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-path", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    dependency_stubs = _install_platform_stubs()
    try:
        module = _load_module(Path(args.app_path), Path(args.project_root))
        client = _http_client(module, _factory_root(Path(args.project_root), Path(args.app_path)))
        if client is None:
            result = {"status": "skipped", "reason": "no supported app adapter"}
        else:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                response = client(args.method, args.path)
            result = {"status": "ok", "response": _response_shape(response), "dependency_stubs": [], "platform_stubs": dependency_stubs}
    except Exception as exc:
        result = {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-4000:],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _install_platform_stubs() -> list[str]:
    if sys.platform != "win32":
        return []
    grp = types.ModuleType("grp")
    grp.getgrgid = lambda gid: types.SimpleNamespace(gr_name=str(gid))
    grp.getgrnam = lambda name: types.SimpleNamespace(gr_name=str(name))
    pwd = types.ModuleType("pwd")
    pwd.getpwuid = lambda uid: types.SimpleNamespace(pw_name=str(uid), pw_dir=".")
    pwd.getpwnam = lambda name: types.SimpleNamespace(pw_name=str(name), pw_dir=".")
    sys.modules.setdefault("grp", grp)
    sys.modules.setdefault("pwd", pwd)
    return ["grp", "pwd"]


def _load_module(path: Path, root: Path) -> Any:
    with _path_front(*_import_roots(root, path)):
        spec = importlib.util.spec_from_file_location("project_probe_target", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


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


def _http_client(module: Any, factory_root: Path | None = None):
    app = getattr(module, "app", None)
    if app is None and callable(getattr(module, "create_app", None)):
        app = _call_app_factory(module.create_app, factory_root)
    if app is None:
        return None
    _prepare_app_for_probe(app)
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
        return lambda method, path: client.request(method, path)
    except Exception:
        return None


def _prepare_app_for_probe(app: Any) -> None:
    _patch_pygments_windows_paths()
    _patch_app_url_for_paths(app)
    if not hasattr(app, "multiplexer"):
        app.multiplexer = _ProbeMultiplexer()
    shared_ctx = getattr(app, "shared_ctx", None)
    if shared_ctx is not None and not hasattr(shared_ctx, "reload_queue"):
        setattr(shared_ctx, "reload_queue", _ProbeQueue())


def _patch_app_url_for_paths(app: Any) -> None:
    app_type = type(app)
    url_for = getattr(app_type, "url_for", None)
    if not callable(url_for) or getattr(app_type, "_cognitive_os_url_for_patch", False):
        return

    @wraps(url_for)
    def patched_url_for(self: Any, *args: Any, **kwargs: Any) -> Any:
        clean = {key: _path_value(value) for key, value in kwargs.items()}
        return url_for(self, *args, **clean)

    setattr(app_type, "url_for", patched_url_for)
    setattr(app_type, "_cognitive_os_url_for_patch", True)


def _path_value(value: Any) -> Any:
    return value.as_posix() if hasattr(value, "as_posix") else value


def _patch_pygments_windows_paths() -> None:
    if sys.platform != "win32":
        return
    try:
        from pygments.formatters import html as pygments_html
    except Exception:
        return
    formatter = pygments_html.HtmlFormatter
    if getattr(formatter, "_cognitive_os_path_patch", False):
        return
    original_init = formatter.__init__

    def __init__(self, **options: Any) -> None:
        cssfile = options.get("cssfile")
        if hasattr(cssfile, "as_posix"):
            options["cssfile"] = cssfile.as_posix()
        original_init(self, **options)

    formatter.__init__ = __init__
    formatter._cognitive_os_path_patch = True


class _ProbeQueue:
    def put(self, item: Any) -> None:
        return None

    def get_nowait(self) -> None:
        raise RuntimeError("probe queue is empty")


class _ProbeMultiplexer:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {}

    def ack(self) -> None:
        return None

    def terminate(self) -> None:
        return None

    def set_serving(self, serving: bool) -> None:
        self.state["serving"] = serving


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


def _shape(payload: Any) -> dict[str, Any]:
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


if __name__ == "__main__":
    raise SystemExit(main())

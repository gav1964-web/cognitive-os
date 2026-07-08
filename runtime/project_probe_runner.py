"""Subprocess HTTP probe runner used by prepared probe environments."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
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
    try:
        module = _load_module(Path(args.app_path), Path(args.project_root))
        client = _http_client(module)
        if client is None:
            result = {"status": "skipped", "reason": "no supported app adapter"}
        else:
            result = {"status": "ok", "response": _response_shape(client(args.method, args.path))}
    except Exception as exc:
        result = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _load_module(path: Path, root: Path) -> Any:
    with _path_front(root, path.parent):
        spec = importlib.util.spec_from_file_location("project_probe_target", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


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

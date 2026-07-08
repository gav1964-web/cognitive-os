"""Static UI smoke checks for rebuilt projects."""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def smoke_test_static_ui(target_dir: Path) -> dict[str, Any]:
    app_path = target_dir / "app.py"
    if not app_path.exists():
        return {"status": "skipped", "reason": "app.py missing", "passed": True}
    if "Flask(" not in app_path.read_text(encoding="utf-8"):
        return {"status": "skipped", "reason": "non-Flask app", "passed": True}
    try:
        module = _load_module(app_path, "target_rebuild_ui_app")
        response = module.app.test_client().get("/")
        body = response.get_data(as_text=True).lower()
    except Exception as exc:  # pragma: no cover - defensive report path
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "passed": False}
    checks = {
        "index_success": response.status_code == 200,
        "mentions_map": "map" in body or "карта" in body,
        "has_api_anchor": "/get_vector_map" in body or "data-api" in body,
        "has_interaction_hint": "search" in body or "incident" in body or "layer" in body,
    }
    return {"status": "ok", "passed": all(checks.values()), "checks": checks, "bytes": len(body)}


def _load_module(path: Path, name: str) -> Any:
    with _path_front(path.parent):
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
def _path_front(path: Path):
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(path))
        except ValueError:
            pass

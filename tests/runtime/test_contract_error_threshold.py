from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.pipeline import load_pipeline
from runtime.registry import CapabilityRegistry


def test_repeated_contract_error_quarantines_capability(tmp_path):
    workspace = _copy_workspace(tmp_path)
    plugin_main = workspace / "plugins" / "parse_title" / "src" / "main.py"
    plugin_main.write_text(
        "from __future__ import annotations\n\n\n"
        "def run(payload: dict[str, object]) -> dict[str, object]:\n"
        "    return {\"wrong\": \"shape\"}\n",
        encoding="utf-8",
    )
    registry = CapabilityRegistry(workspace)
    registry.reset_from_plugins()
    pipeline = load_pipeline(workspace / "pipelines" / "fetch_parse_save.json")
    payload = {"url": "mock://ok", "output_path": "artifacts/outputs/contract_error.json"}

    _clear_plugin_modules("plugins")
    first = execute_pipeline(workspace, pipeline, payload)
    _clear_plugin_modules("plugins")
    second = execute_pipeline(workspace, pipeline, payload)

    registry.load()
    assert first["interrupt"]["capability_status"] == "active"
    assert second["status"] == "ok"
    assert second["outputs"]["parse"] == {"title": "Cognitive OS MVP"}
    assert registry.capabilities["parse_title"].lifecycle_status == "quarantined"


def _copy_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    for name in ("runtime", "tools", "plugins", "pipelines", "registry", "generated"):
        shutil.copytree(source / name, workspace / name, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    return workspace


def _clear_plugin_modules(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            sys.modules.pop(name, None)

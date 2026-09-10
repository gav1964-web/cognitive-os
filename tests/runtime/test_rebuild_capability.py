from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_rebuild_quarantined_capability_promotes_repaired_plugin(tmp_path):
    workspace = _copy_workspace(tmp_path)
    sys.path.insert(0, str(workspace))
    from runtime.registry import CapabilityRegistry

    registry = CapabilityRegistry(workspace)
    registry.reset_from_plugins()
    registry.mark_status("parse_title", "quarantined", reason="test")

    tool = workspace / "tools" / "rebuild_capability.py"
    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", "parse_title"],
        check=True,
        capture_output=True,
        text=True,
    )

    registry_data = json.loads((workspace / "registry" / "capabilities.json").read_text(encoding="utf-8"))
    parse_title = next(item for item in registry_data["capabilities"] if item["id"] == "parse_title")
    assert "rebuilt" in result.stdout
    assert parse_title["lifecycle_status"] == "active"
    assert "rebuilt parser recovered" in (workspace / "plugins" / "parse_title" / "src" / "main.py").read_text(
        encoding="utf-8"
    )
    assert list((workspace / "artifacts" / "promotions").glob("parse_title_*.json"))


def _copy_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    for name in ("runtime", "tools", "plugins", "pipelines", "registry", "generated"):
        src = source / name
        dst = workspace / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        else:
            dst.mkdir(parents=True, exist_ok=True)
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    return workspace

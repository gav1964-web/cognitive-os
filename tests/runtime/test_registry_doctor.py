from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_registry_doctor_detects_hash_drift(tmp_path):
    workspace = tmp_path / "workspace"
    root = Path(__file__).resolve().parents[2]
    for name in ("runtime", "tools", "plugins", "registry"):
        shutil.copytree(root / name, workspace / name, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    sys.path.insert(0, str(workspace))
    from runtime.registry import CapabilityRegistry

    CapabilityRegistry(workspace).reset_from_plugins()
    registry_path = workspace / "registry" / "capabilities.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    data["capabilities"][0]["version_hash"] = "sha256:stale"
    registry_path.write_text(json.dumps(data), encoding="utf-8")
    tool = workspace / "tools" / "registry_doctor.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "hash_drift" in result.stdout

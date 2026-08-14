from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture()
def runtime_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "runtime_workspace"
    for name in ("config", "pipelines", "plugins", "registry", "roles", "runtime", "tools"):
        shutil.copytree(source / name, workspace / name)
    shutil.copy2(source / "run_mvp.py", workspace / "run_mvp.py")
    return workspace

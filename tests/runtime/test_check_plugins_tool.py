from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_check_plugins_tool_passes_current_plugins():
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "check_plugins.py"
    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"status": "ok"' in result.stdout
    assert "parse_title" in result.stdout

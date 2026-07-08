from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_generator_creates_candidate_layout(tmp_path):
    tool = Path(__file__).resolve().parents[2] / "tools" / "generate_plugin_candidate.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(tmp_path), "--id", "normalize_text"],
        check=True,
        capture_output=True,
        text=True,
    )

    candidate = tmp_path / "generated" / "candidates" / "normalize_text"
    assert "created" in result.stdout
    assert (candidate / "plugin.json").exists()
    assert (candidate / "spec.json").exists()
    assert (candidate / "requirements.lock").exists()
    assert (candidate / "schemas" / "input.json").exists()
    assert (candidate / "schemas" / "output.json").exists()
    assert (candidate / "src" / "main.py").exists()
    assert (candidate / "tests" / "test_contract.py").exists()

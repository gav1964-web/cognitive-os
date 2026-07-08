from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_generate_and_validate_capability_spec(tmp_path):
    root = Path(__file__).resolve().parents[2]
    generate = root / "tools" / "generate_capability_spec.py"
    validate = root / "tools" / "validate_capability_spec.py"

    result = subprocess.run(
        [sys.executable, str(generate), "--root", str(tmp_path), "--id", "candidate_spec", "--purpose", "Echo values"],
        check=True,
        capture_output=True,
        text=True,
    )
    spec_path = Path(json.loads(result.stdout)["spec"])
    checked = subprocess.run(
        [sys.executable, str(validate), "--spec", str(spec_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "created" in result.stdout
    assert json.loads(checked.stdout)["status"] == "ok"

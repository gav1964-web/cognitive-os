from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime.knowledge import knowledge_preflight


ROOT = Path(__file__).resolve().parents[2]


def test_knowledge_preflight_blocks_xls_without_backend():
    result = knowledge_preflight(
        "Convert XLS file from $input.input_path to CSV file at $input.output_path",
        {"input_path": "book.xls", "output_path": "out.csv"},
    )

    assert result["status"] == "blocked"
    assert result["knowledge_gaps"][0]["question"].startswith("Is a legacy .xls backend")
    assert result["knowledge_artifacts"][0]["source"] == "inspect_installed_packages"
    assert result["route_override"]["action"] == "STOP_UNSUPPORTED"


def test_goal_run_records_knowledge_gap_before_xls_execution(tmp_path):
    shutil.copytree(ROOT / "plugins", tmp_path / "plugins")
    shutil.copytree(ROOT / "registry", tmp_path / "registry")
    Path(tmp_path / "book.xls").write_bytes(b"fake xls")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "goal_run.py"),
            "--root",
            str(tmp_path),
            "--goal",
            "Convert XLS file from $input.input_path to CSV file at $input.output_path",
            "--execute",
            "--input-json",
            json.dumps({"input_path": "book.xls", "output_path": "out.csv"}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))

    assert payload["level4_decision"]["action"] == "STOP_UNSUPPORTED"
    assert payload["level4_decision"]["reason_code"] == "L4_KNOWLEDGE_GAP_UNRESOLVED"
    assert "execution" not in payload
    assert report["knowledge_gaps"]
    assert report["knowledge_artifacts"][0]["extracted_fact"] == "legacy .xls backend is not available"

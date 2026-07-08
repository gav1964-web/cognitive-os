"""Probe the MVP Knowledge Gap Loop."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    payload = {"input_path": "artifacts/outputs/knowledge_probe/book.xls", "output_path": "artifacts/outputs/knowledge_probe/out.csv"}
    path = root / payload["input_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake xls")
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "goal_run.py"),
            "--root",
            str(root),
            "--goal",
            "Convert XLS file from $input.input_path to CSV file at $input.output_path",
            "--execute",
            "--input-json",
            json.dumps(payload),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    artifact = (report.get("knowledge_artifacts") or [{}])[0]
    ok = (
        dict(report.get("level4_decision", {})).get("reason_code") == "L4_KNOWLEDGE_GAP_UNRESOLVED"
        and bool(report.get("knowledge_gaps"))
        and artifact.get("source") == "inspect_installed_packages"
        and "execution" not in report
    )
    print(json.dumps({"status": "ok" if ok else "failed", "report_path": report.get("report_path")}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

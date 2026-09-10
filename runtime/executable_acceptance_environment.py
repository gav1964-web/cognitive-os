"""Build acceptance harness evidence inside an approved Python environment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


_PROBE = (
    "import json,sys;"
    "sys.path.insert(0,sys.argv[1]);"
    "from pathlib import Path;"
    "from runtime.executable_acceptance_support import harness_summary;"
    "rows=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'));"
    "print(json.dumps(harness_summary(Path(sys.argv[2]),rows),sort_keys=True))"
)


def environment_harness_summary(
    *, root: Path, project_dir: Path, obligations_path: Path, python_executable: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            str(python_executable), "-c", _PROBE, root.resolve().as_posix(),
            project_dir.resolve().as_posix(), obligations_path.resolve().as_posix(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        return {
            "version": "executable_acceptance_harness_v0.4",
            "signal_strength": "environment_probe_failed",
            "callable_harness_count": 0,
            "callable_targets": [],
            "strict_negative_targets": [],
            "skipped_targets": [],
            "skipped_reason_counts": {"environment_harness_probe_failed": 1},
            "environment_probe": {
                "status": "failed",
                "python": python_executable.resolve().as_posix(),
                "stderr_tail": result.stderr[-1200:],
            },
        }
    try:
        summary = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError, TypeError):
        return {
            "version": "executable_acceptance_harness_v0.4",
            "signal_strength": "environment_probe_failed",
            "callable_harness_count": 0,
            "callable_targets": [],
            "strict_negative_targets": [],
            "skipped_targets": [],
            "skipped_reason_counts": {"environment_harness_output_invalid": 1},
        }
    summary["environment_probe"] = {
        "status": "passed",
        "python": python_executable.resolve().as_posix(),
    }
    return summary

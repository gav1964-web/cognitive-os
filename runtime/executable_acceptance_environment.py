"""Build acceptance harness evidence inside an approved Python environment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from cognitive_replay.process import run_command, isolated_environment


_PROBE = (
    "import json,sys;"
    "sys.path.insert(0,sys.argv[1]);"
    "from pathlib import Path;"
    "sys.path.extend(str(p) for p in (Path(sys.argv[1])/'packages').glob('*/src'));"
    "from runtime.executable_acceptance_support import harness_summary;"
    "rows=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'));"
    "print(json.dumps(harness_summary(Path(sys.argv[2]),rows),sort_keys=True))"
)


def environment_harness_summary(
    *, root: Path, project_dir: Path, obligations_path: Path, python_executable: Path,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise ValueError('invalid_harness_probe_timeout')
    # The workspace may be a temporary project root. Load the same COS runtime
    # that the controller imported, just as generated acceptance already does.
    runtime_root = Path(__file__).resolve().parents[1]
    result = run_command(
        [
            str(python_executable), "-c", _PROBE, runtime_root.as_posix(),
            project_dir.resolve().as_posix(), obligations_path.resolve().as_posix(),
        ],
        cwd=project_dir.resolve(), timeout=timeout_seconds,
        env=isolated_environment(obligations_path.parent / 'probe_environment', python_executable),
    )
    if result['returncode'] != 0:
        return {
            "version": "executable_acceptance_harness_v0.4",
            "signal_strength": "environment_probe_failed",
            "callable_harness_count": 0,
            "callable_targets": [],
            "strict_negative_targets": [],
            "skipped_targets": [],
            "skipped_reason_counts": {"environment_harness_probe_failed": 1},
            "environment_probe": {
                "status": "timed_out" if result['returncode'] == 124 else "failed",
                "returncode": result['returncode'],
                "timeout_seconds": timeout_seconds,
                "python": python_executable.resolve().as_posix(),
                "stderr_tail": result['stderr'][-1200:],
            },
        }
    try:
        summary = json.loads(result['stdout'].strip().splitlines()[-1])
        if not isinstance(summary, dict) or not {
            'signal_strength', 'callable_harness_count', 'skipped_reason_counts', 'skipped_targets',
        }.issubset(summary):
            raise TypeError('invalid_harness_summary')
    except (IndexError, json.JSONDecodeError, TypeError):
        return {
            "version": "executable_acceptance_harness_v0.4",
            "signal_strength": "environment_probe_failed",
            "callable_harness_count": 0,
            "callable_targets": [],
            "strict_negative_targets": [],
            "skipped_targets": [],
            "skipped_reason_counts": {"environment_harness_output_invalid": 1},
            "environment_probe": {"status": "failed", "reason": "invalid_harness_summary"},
        }
    summary["environment_probe"] = {
        "status": "passed",
        "python": python_executable.resolve().as_posix(),
    }
    return summary

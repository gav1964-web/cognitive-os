"""Run generated acceptance checks with the host or an approved Python."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


_STDLIB_RUNNER = """import runpy,sys,traceback
namespace = runpy.run_path(sys.argv[1])
failures = []
for name in sorted(key for key in namespace if key.startswith('test_')):
    try:
        namespace[name]()
    except BaseException:
        failures.append(name)
        traceback.print_exc()
print(f'{len(failures)} failed' if failures else 'acceptance passed')
raise SystemExit(1 if failures else 0)
"""


def run_acceptance_command(
    *, python_executable: Path | None, tests_dir: Path, test_path: Path, cwd: Path,
) -> dict[str, Any]:
    if python_executable is None:
        command = [sys.executable, "-m", "pytest", str(tests_dir.resolve()), "-q"]
        runner = "pytest"
    else:
        runner_path = (cwd / "run_acceptance.py").resolve()
        runner_path.write_text(_STDLIB_RUNNER, encoding="utf-8")
        command = [str(python_executable), str(runner_path), str(test_path.resolve())]
        runner = "stdlib"
    result = _run_command(command, cwd=cwd)
    result["runner"] = runner
    result["python"] = Path(command[0]).resolve().as_posix()
    return result


def _run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"], env["PYTHONUTF8"] = "utf-8", "1"
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env, timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "status": "timed_out",
            "timeout_seconds": 120,
            "stdout_tail": _tail(exc.stdout),
            "stderr_tail": _tail(exc.stderr),
        }
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _tail(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-2000:]

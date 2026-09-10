"""Bounded subprocesses used by historical qualification."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .bounded_process import _run_bounded_process


def run_command(
    command: list[str], *, cwd: Path, timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        run = _run_bounded_process(
            command, cwd=cwd, timeout=timeout, env=dict(os.environ) if env is None else env,
        )
        return {"command": command, "returncode": run.returncode,
                "stdout": run.stdout, "stderr": run.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"command": command, "returncode": 124,
                "stdout": _text(exc.stdout), "stderr": _text(exc.stderr)}


def isolated_environment(directory: Path, python: Path) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "PYTEST", "COV_CORE_"))
        and key.upper() != "VIRTUAL_ENV"
    }
    directory.mkdir(parents=True, exist_ok=True)
    env.update({
        "PATH": str(python.parent) + os.pathsep + env.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": "",
        "PIP_NO_INDEX": "1", "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "TMP": str(directory), "TEMP": str(directory), "TMPDIR": str(directory),
    })
    return env


def _text(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""

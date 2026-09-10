"""Bounded local Git reads; legacy error name preserved for compatibility."""
from __future__ import annotations
import subprocess
from pathlib import Path

class HistoricalDefectMiningError(ValueError):
    """Raised when local historical mining would violate its evidence boundary."""


def _git_snapshot(project: Path) -> dict[str, str]:
    try:
        shallow = _git(project, ["rev-parse", "--is-shallow-repository"]).strip()
        return {
            "status": _git(project, ["status", "--porcelain=v1"]).strip(),
            "revision": _git(project, ["rev-parse", "HEAD"]).strip(),
            "origin": _git(project, ["remote", "get-url", "origin"]).strip(),
            "shallow": shallow,
            "history_count": _git(project, ["rev-list", "--count", "HEAD"]).strip(),
        }
    except HistoricalDefectMiningError:
        return {}


def _git(project: Path, args: list[str], timeout: int = 20) -> str:
    command = ["git", "-c", f"safe.directory={project.as_posix()}", "-C", str(project), *args]
    try:
        run = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HistoricalDefectMiningError("local Git metadata unavailable") from exc
    if run.returncode != 0:
        raise HistoricalDefectMiningError("local Git command failed")
    return run.stdout


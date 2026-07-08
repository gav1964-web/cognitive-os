"""Cleanup helpers for generated rebuild projects."""

from __future__ import annotations

import shutil
from pathlib import Path


def clean_generated_runtime_artifacts(output_dir: Path) -> None:
    for path in output_dir.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    for path in output_dir.rglob(".pytest_cache"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

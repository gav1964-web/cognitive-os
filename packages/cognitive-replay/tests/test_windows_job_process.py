from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cognitive_replay.windows_job_process import run_windows_job


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows job-object process boundary")


def test_job_preserves_output_and_exit_code(tmp_path: Path) -> None:
    result = run_windows_job(
        [sys.executable, "-X", "utf8", "-c", "print('готово');raise SystemExit(7)"],
        cwd=tmp_path, env=dict(os.environ), timeout=10,
    )

    assert result.returncode == 7
    assert result.stdout.strip() == "готово"


def test_command_cannot_start_before_job_admission(tmp_path: Path, monkeypatch) -> None:
    import cognitive_replay.windows_job_process as runner

    marker = tmp_path / "executed.txt"

    def refuse(self, process):
        raise OSError("job assignment refused")

    monkeypatch.setattr(runner._Job, "assign", refuse)
    with pytest.raises(OSError, match="assignment refused"):
        run_windows_job(
            [sys.executable, "-c", "from pathlib import Path;Path(" + repr(str(marker)) + ").touch()"],
            cwd=tmp_path, env=dict(os.environ), timeout=10,
        )
    assert not marker.exists()


def test_job_closes_descendants_after_successful_parent_exit(tmp_path: Path) -> None:
    marker = tmp_path / "leaked.txt"
    child = "import time,pathlib;time.sleep(1);pathlib.Path(" + repr(str(marker)) + ").touch()"
    parent = (
        "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(child) + "],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    result = run_windows_job([sys.executable, "-c", parent], cwd=tmp_path, env=dict(os.environ), timeout=10)
    subprocess.run([sys.executable, "-c", "import time;time.sleep(2)"], timeout=5, check=True)

    assert result.returncode == 0
    assert not marker.exists()

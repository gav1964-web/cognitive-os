from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.runtime.test_promote_candidate import _copy_workspace, _generate


def test_promote_rejects_candidate_with_forbidden_import(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "unsafe_candidate")
    main_py = workspace / "generated" / "candidates" / "unsafe_candidate" / "src" / "main.py"
    main_py.write_text("import subprocess\n\ndef run(payload):\n    return {\"value\": \"x\"}\n", encoding="utf-8")
    tool = workspace / "tools" / "promote_candidate.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", "unsafe_candidate"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "forbidden import" in result.stderr


def test_promote_rejects_candidate_without_spec(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "unsafe_candidate")
    (workspace / "generated" / "candidates" / "unsafe_candidate" / "spec.json").unlink()
    tool = workspace / "tools" / "promote_candidate.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", "unsafe_candidate"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "spec.json" in result.stderr


def test_promote_rejects_unpinned_dependency(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "unsafe_candidate")
    (workspace / "generated" / "candidates" / "unsafe_candidate" / "requirements.lock").write_text(
        "requests\n",
        encoding="utf-8",
    )
    tool = workspace / "tools" / "promote_candidate.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", "unsafe_candidate"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "pinned" in result.stderr


def test_promote_rejects_filesystem_call_without_permission(tmp_path):
    workspace = _copy_workspace(tmp_path)
    _generate(workspace, "unsafe_candidate")
    main_py = workspace / "generated" / "candidates" / "unsafe_candidate" / "src" / "main.py"
    main_py.write_text(
        "from pathlib import Path\n\n"
        "def run(payload):\n"
        "    Path('x').write_text('bad')\n"
        "    return {\"value\": \"x\"}\n",
        encoding="utf-8",
    )
    tool = workspace / "tools" / "promote_candidate.py"

    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(workspace), "--id", "unsafe_candidate"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "filesystem call requires" in result.stderr

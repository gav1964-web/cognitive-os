from __future__ import annotations

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def test_executable_acceptance_allows_none_for_optional_result(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text("def lookup():\n    return None\n", encoding="utf-8")
    plan = _plan("module.py:lookup", {}, malformed=False)
    obligation = plan["executable_acceptance"]["obligations"][0]
    obligation["expect"] = {"result": "Optional[str]"}

    result = run_executable_acceptance(
        root=tmp_path, project_dir=project, test_plan=plan, work_dir=tmp_path / "work"
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"

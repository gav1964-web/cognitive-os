from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_isolation import load_source_isolated_method
from tests.runtime.test_executable_acceptance import _plan


def _source(root: Path) -> Path:
    path = root / "module.py"
    path.write_text(
        "class Handler:\n"
        "    @staticmethod\n"
        "    def __format_value(value):\n"
        "        return 'value={}'.format(value)\n",
        encoding="utf-8",
    )
    return path


def test_source_isolation_loads_name_mangled_static_method(tmp_path: Path):
    loaded = load_source_isolated_method(_source(tmp_path), "__format_value")

    assert loaded["reason"] == ""
    assert loaded["callable"](3) == "value=3"


def test_acceptance_executes_name_mangled_static_method(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    _source(project)

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:__format_value", {"value": 3}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"

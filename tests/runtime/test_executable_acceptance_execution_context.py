from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def test_executable_acceptance_isolates_argparse_from_pytest_arguments(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "cli.py").write_text(
        "import argparse\n\n"
        "def parse_args():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--count', type=int, default=3)\n"
        "    return parser.parse_args()\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("cli.py:parse_args", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.executable_acceptance_target_resolution import resolve_target_path
from tests.runtime.test_executable_acceptance import _plan


def test_resolves_unique_package_relative_target_suffix(tmp_path: Path):
    target = tmp_path / "python" / "example" / "service.py"
    target.parent.mkdir(parents=True)
    target.write_text("def run():\n    return True\n", encoding="utf-8")

    result = resolve_target_path(tmp_path, "example/service.py")

    assert result["reason"] == ""
    assert result["path"] == target.resolve()
    assert result["path_text"] == "python/example/service.py"


def test_rejects_ambiguous_package_relative_target_suffix(tmp_path: Path):
    for root_name in ("first", "second"):
        target = tmp_path / root_name / "example" / "service.py"
        target.parent.mkdir(parents=True)
        target.write_text("def run():\n    return True\n", encoding="utf-8")

    result = resolve_target_path(tmp_path, "example/service.py")

    assert result["reason"] == "target_file_ambiguous"
    assert "first/example/service.py" in result["detail"]
    assert "second/example/service.py" in result["detail"]


def test_acceptance_executes_uniquely_resolved_target(tmp_path: Path):
    project = tmp_path / "project"
    target = project / "python" / "example" / "service.py"
    target.parent.mkdir(parents=True)
    target.write_text("def parse(url: str):\n    return {'parsed_url': url}\n", encoding="utf-8")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("example/service.py:parse", {"url": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["resolved_target_paths"] == {
        "example/service.py:parse": "python/example/service.py"
    }

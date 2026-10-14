from runtime.executable_acceptance import run_executable_acceptance


def test_isolated_callable_preserves_named_tuple_without_type_only_module(tmp_path):
    project = tmp_path / "project"
    package = project / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "model.py").write_text(
        "from .worker import Point\nclass Record: pass\n", encoding="utf-8"
    )
    (package / "worker.py").write_text(
        "from typing import NamedTuple\n"
        "from . import model as db_cli\n\n"
        "class Point(NamedTuple):\n    value: str\n\n"
        "class Result:\n"
        "    def __init__(self, point: Point, record: db_cli.Record):\n"
        "        self.point = point\n        self.record = record\n\n"
        "def load(value: str) -> Result:\n    return Result(Point(value), value)\n",
        encoding="utf-8",
    )
    plan = {"executable_acceptance": {"obligations": [{
        "id": "EA-1", "target": "pkg/worker.py:load",
        "kind": "positive_contract_case", "given": {"value": "sample"},
        "expect": {"result": "InferredOutput"},
    }]}}

    result = run_executable_acceptance(
        root=tmp_path, project_dir=project, test_plan=plan, work_dir=tmp_path / "work"
    )

    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["pkg/worker.py:load"]

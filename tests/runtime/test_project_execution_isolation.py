import sys
from types import ModuleType

from runtime.project_execution_isolation import isolated_project_execution


def test_project_execution_isolation_restores_import_and_process_arguments():
    original_json = sys.modules["json"]
    original_path = list(sys.path)
    original_argv = list(sys.argv)

    with isolated_project_execution():
        sys.modules["project_probe_only"] = ModuleType("project_probe_only")
        sys.modules["json"] = ModuleType("json")
        sys.path.insert(0, "project-probe-path")
        sys.argv[:] = ["project-cli", "--unsafe"]

    assert "project_probe_only" not in sys.modules
    assert sys.modules["json"] is original_json
    assert sys.path == original_path
    assert sys.argv == original_argv

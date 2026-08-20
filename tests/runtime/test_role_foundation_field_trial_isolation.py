from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

from runtime.role_foundation_field_trial import run_role_foundation_field_trial


def test_field_trial_isolates_imported_modules_between_projects(tmp_path: Path):
    projects = [tmp_path / "first", tmp_path / "second"]
    for project in projects:
        (project / ".git").mkdir(parents=True)
    module_name = "_cognitive_os_field_trial_leak"
    observed: list[bool] = []

    def fake_case(**_kwargs):
        observed.append(module_name in sys.modules)
        sys.modules[module_name] = types.ModuleType(module_name)
        return {"project": "fixture", "status": "out_of_scope"}

    with patch("runtime.role_foundation_field_trial._run_case", side_effect=fake_case):
        run_role_foundation_field_trial(root=tmp_path, project_roots=projects)

    assert observed == [False, False]
    assert module_name not in sys.modules

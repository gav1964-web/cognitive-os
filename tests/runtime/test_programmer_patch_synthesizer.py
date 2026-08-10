from __future__ import annotations

import json
from pathlib import Path

from runtime.patch_synthesis_policy import required_input_guard_recipe
from runtime.programmer_patch_synthesizer import _copy_project
from runtime.programmer_executor import run_programmer_executor


def test_required_input_guard_recipe_is_config_backed():
    recipe = required_input_guard_recipe()

    assert recipe["reason"] == "required_input_guard_synthesized"
    assert recipe["operation_kind"] == "insert_required_input_guard"
    assert "self" in recipe["ignored_signature_parameters"]


def test_programmer_executor_synthesizes_literal_return_for_stub(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def status():\n    pass\n", encoding="utf-8")
    plan = {
        "implementation_target": {"candidate": "main.py:status"},
        "patch_intent": {"target_symbol": "main.py:status"},
        "writable_scope": ["main.py:status"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:status",
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"return_value": "ready"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:status",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                }
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "return_literal_stub_synthesized"
    assert patch["patch_strategy"]["patch_quality"]["level"] == "contract_backed_return_literal"
    assert patch["patch_strategy"]["solution_patterns"][0]["id"] == "executor_pattern_contract_backed_stub_completion"
    assert patch["patches"][0]["kind"] == "replace_stub_with_literal_return"
    assert patch["patches"][0]["return_evidence"]["source"] == "contract_return_literal_case"
    assert "return 'ready'" in source


def test_programmer_executor_synthesizes_literal_return_for_notimplemented(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def status():\n    raise NotImplementedError\n", encoding="utf-8")
    plan = {
        "implementation_target": {"candidate": "main.py:status"},
        "patch_intent": {"target_symbol": "main.py:status"},
        "writable_scope": ["main.py:status"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:status",
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"return_value": "ready"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:status",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "return_literal_notimplemented_synthesized"
    assert patch["patch_strategy"]["patch_quality"]["level"] == "contract_backed_notimplemented_return"
    assert patch["patch_strategy"]["solution_patterns"][0]["id"] == "executor_pattern_contract_backed_notimplemented_completion"
    assert patch["patches"][0]["kind"] == "replace_notimplemented_with_literal_return"
    assert "return 'ready'" in source


def test_programmer_executor_synthesizes_string_transform_from_contract(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")
    plan = {
        "implementation_target": {"candidate": "main.py:normalize"},
        "patch_intent": {"target_symbol": "main.py:normalize"},
        "writable_scope": ["main.py:normalize"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:normalize",
                    "kind": "positive_contract_case",
                    "given": {"value": " Sample "},
                    "expect": {"return_value": "sample"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:normalize",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "contract_transform_identity_return_synthesized"
    assert patch["patch_strategy"]["patch_quality"]["level"] == "contract_backed_identity_transform"
    assert patch["patch_strategy"]["solution_patterns"][0]["id"] == "executor_pattern_contract_backed_identity_transform"
    assert patch["patches"][0]["transform"] == "strip_lower"
    assert "return value.strip().lower()" in source


def test_programmer_patch_sandbox_copy_tolerates_disappearing_files(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run(value):\n    return value\n", encoding="utf-8")
    missing = project / "missing.py"
    sandbox = tmp_path / "sandbox"

    original_walk = __import__("os").walk

    def fake_walk(path, onerror=None):
        yield str(project), [], ["main.py", "missing.py"]

    import runtime.programmer_patch_synthesizer as module

    module.os.walk = fake_walk
    try:
        _copy_project(project, sandbox)
    finally:
        module.os.walk = original_walk

    assert (sandbox / "main.py").is_file()
    assert not missing.exists()


def test_programmer_executor_synthesizes_guard_for_unique_method(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "class Renderer:\n"
        "    def render(self, node, frame):\n"
        "        return str(node)\n",
        encoding="utf-8",
    )
    plan = {
        "implementation_target": {"candidate": "main.py:render"},
        "patch_intent": {"target_symbol": "main.py:render"},
        "writable_scope": ["main.py:render"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:render",
                    "kind": "positive_contract_case",
                    "given": {"node": "n", "frame": "f"},
                    "expect": {"result": "string"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "contract_negative_missing_input",
                    "target": "main.py:render",
                    "kind": "malformed_input_case",
                    "given": {"return_value": "sample"},
                    "expect": {"error": "controlled_validation_error"},
                    "oracle": "missing_required_input_rejected",
                },
                {
                    "id": "OBL-003",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:render",
                    "kind": "side_effect_scope_case",
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    sandbox_main = Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py"
    source = sandbox_main.read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["status"] == "prepared"
    assert "if node is None:" in source
    assert "if frame is None:" in source
    assert patch["patches"][0]["guard_evidence"]["source"] == "signature_required_parameters"


def test_programmer_executor_synthesizes_guard_from_signature_when_contract_is_empty(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def analyze(\n"
        "    *,\n"
        "    param_name,\n"
        "    annotation,\n"
        "    value,\n"
        "    is_path_param,\n"
        "):\n"
        "    return {'name': param_name}\n",
        encoding="utf-8",
    )
    plan = {
        "implementation_target": {"candidate": "main.py:analyze"},
        "patch_intent": {"target_symbol": "main.py:analyze"},
        "writable_scope": ["main.py:analyze"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "target": "main.py:analyze",
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"result": "declared_output"},
                }
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert patch["patch_synthesis"]["status"] == "prepared"
    assert "):\n    if param_name is None:" in source
    assert "if param_name is None:" in source
    assert "if is_path_param is None:" in source


def test_programmer_executor_synthesizes_guard_for_positional_only_parameter(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def path_template(template, /, **kwargs):\n"
        "    return template.format(**kwargs) if kwargs else template\n",
        encoding="utf-8",
    )
    plan = {
        "implementation_target": {"candidate": "main.py:path_template"},
        "patch_intent": {"target_symbol": "main.py:path_template"},
        "writable_scope": ["main.py:path_template"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:path_template",
                    "kind": "positive_contract_case",
                    "given": {},
                    "expect": {"result": "str"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:path_template",
                    "kind": "side_effect_scope_case",
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                }
            ]
        }
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert "if template is None:" in source
    assert "\"template\" not in kwargs" not in source

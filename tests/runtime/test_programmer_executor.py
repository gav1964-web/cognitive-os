from __future__ import annotations

from tests.runtime.programmer_executor_helpers import *

def test_programmer_executor_writes_patch_package_and_test_result(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize_text(text: str) -> str:\n    return text.strip().lower()\n", encoding="utf-8")
    spec = {"artifact_type": "TechnicalSpec", "role": "spec_writer"}
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": "main.py:normalize_text"},
        "implementation_blueprint": {"artifact_type": "ImplementationBlueprint", "target": "main.py:normalize_text"},
        "patch_intent": {"artifact_type": "PatchIntent", "mode": "sandbox_first", "target_symbol": "main.py:normalize_text"},
        "executor_handoff": {"artifact_type": "ExecutorHandoff", "recommended_tool": "tools/apply_implementation_plan.py"},
        "writable_scope": ["main.py:normalize_text"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "executable_acceptance": {
            "status": "ready",
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:normalize_text",
                    "kind": "positive_contract_case",
                    "given": {"text": " Sample "},
                    "expect": {"result": "string"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "contract_negative_missing_input",
                    "target": "main.py:normalize_text",
                    "kind": "malformed_input_case",
                    "given": {},
                    "expect": {"error": "controlled_validation_error"},
                    "oracle": "missing_required_input_rejected",
                },
                {
                    "id": "OBL-003",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:normalize_text",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ],
        },
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
        execution_base_dir=tmp_path / "custom-executions",
    )

    assert result["status"] == "ok"
    assert result["source_code_changes"] is False
    assert Path(result["execution_dir"]).parent == tmp_path / "custom-executions"
    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    task_tree = json.loads(Path(result["task_tree_path"]).read_text(encoding="utf-8"))
    assert patch["artifact_type"] == "PatchPackage"
    assert task_tree["artifact_type"] == "ProgrammerTaskTree"
    assert task_tree["role"] == "task_tree_builder"
    assert task_tree["programmer_handoff"]["next_role"] == "programmer_executor"
    assert patch["programmer_task_tree"]["summary"]["node_count"] == 6
    assert patch["programmer_task_tree"]["summary"]["acceptance_node_count"] == 3
    assert patch["implementation_blueprint"]["artifact_type"] == "ImplementationBlueprint"
    assert patch["patch_intent"]["mode"] == "sandbox_first"
    assert patch["executor_handoff"]["recommended_tool"] == "tools/apply_implementation_plan.py"
    assert patch["snapshot"][0]["status"] == "copied"
    assert patch["patch_synthesis"]["status"] == "prepared"
    assert patch["patches"][0]["kind"] == "insert_required_input_guard"
    assert test_result["artifact_type"] == "TestResult"
    assert test_result["programmer_task_tree"]["target"] == "main.py:normalize_text"
    assert test_result["summary"]["passed"] == 1
    assert test_result["commands"][1]["reason"] == "redundant_unscoped_compileall_replaced_by_project_scoped_check"
    assert test_result["commands"][0]["kind"] == "project_scoped_py_compile"
    assert test_result["commands"][0]["scope"] == ["main.py"]
    assert test_result["executable_acceptance_result"]["status"] == "passed"
    assert Path(test_result["executable_acceptance_result"]["generated_tests"][0]).is_file()


def test_programmer_executor_synthesizes_required_input_guard_in_sandbox(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def loose(**kwargs):\n    return 'ok'\n", encoding="utf-8")
    spec = {"artifact_type": "TechnicalSpec", "role": "spec_writer"}
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": "main.py:loose"},
        "patch_intent": {"artifact_type": "PatchIntent", "mode": "sandbox_first", "target_symbol": "main.py:loose"},
        "writable_scope": ["main.py:loose"],
        "expected_files": ["main.py"],
        "verification_commands": [],
    }
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "executable_acceptance": {
            "status": "ready",
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:loose",
                    "kind": "positive_contract_case",
                    "given": {"text": "sample"},
                    "expect": {"result": "string"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "contract_negative_missing_input",
                    "target": "main.py:loose",
                    "kind": "malformed_input_case",
                    "given": {},
                    "expect": {"error": "controlled_validation_error"},
                    "oracle": "missing_required_input_rejected",
                },
                {
                    "id": "OBL-003",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:loose",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ],
        },
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    sandbox_main = Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py"

    assert result["status"] == "ok"
    assert result["source_code_changes"] is False
    assert (project / "main.py").read_text(encoding="utf-8") == "def loose(**kwargs):\n    return 'ok'\n"
    assert patch["patch_synthesis"]["status"] == "prepared"
    assert patch["patches"][0]["required_inputs"] == ["text"]
    assert patch["patches"][0]["guard_evidence"]["source"] == "contract_missing_input_case"
    assert 'if "text" not in kwargs:' in sandbox_main.read_text(encoding="utf-8")
    assert test_result["execution_project"] == patch["patch_synthesis"]["sandbox_project"]
    assert test_result["commands"][0]["kind"] == "project_scoped_py_compile"
    assert test_result["commands"][0]["scope"] == ["main.py"]
    assert test_result["executable_acceptance_result"]["status"] == "passed"


def test_programmer_executor_synthesizes_guard_for_async_function(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("async def fetch(host: str):\n    return host\n", encoding="utf-8")
    plan = {
        "implementation_target": {"candidate": "main.py:fetch"},
        "patch_intent": {"target_symbol": "main.py:fetch"},
        "writable_scope": ["main.py:fetch"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:fetch",
                    "kind": "positive_contract_case",
                    "given": {"host": "example.com"},
                    "expect": {"result": "string"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "contract_negative_missing_input",
                    "target": "main.py:fetch",
                    "kind": "malformed_input_case",
                    "given": {},
                    "expect": {"error": "controlled_validation_error"},
                    "oracle": "missing_required_input_rejected",
                },
                {
                    "id": "OBL-003",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:fetch",
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
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["status"] == "prepared"
    assert "if host is None:" in sandbox_main.read_text(encoding="utf-8")
    assert (project / "main.py").read_text(encoding="utf-8") == "async def fetch(host: str):\n    return host\n"


def test_programmer_executor_blocks_source_apply_in_mvp(tmp_path: Path):
    result = run_programmer_executor(
        root=tmp_path,
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "main.py:normalize_text"}},
        test_plan={},
        apply_source=True,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "source_edit_apply_not_enabled_in_mvp"
    assert Path(result["no_patch_package_path"]).is_file()
    assert Path(result["blocked_execution_report_path"]).is_file()


def test_programmer_executor_writes_formal_blocked_handoff_artifacts(tmp_path: Path):
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "status": "blocked_no_safe_candidate",
        "contract_test_matrix": [{"id": "CONTRACT-BLOCK-001", "target": "blocked_no_safe_candidate", "direction": "blocked_handoff"}],
    }
    result = run_programmer_executor(
        root=tmp_path,
        project_dir=tmp_path,
        technical_spec={"artifact_type": "TechnicalSpec", "role": "spec_writer"},
        implementation_plan={
            "artifact_type": "ImplementationPlan",
            "role": "implementer",
            "implementation_target": {"status": "blocked_no_safe_candidate", "candidate": None},
            "patch_intent": {"artifact_type": "PatchIntent", "status": "blocked_no_safe_candidate"},
        },
        test_plan=test_plan,
    )
    no_patch = json.loads(Path(result["no_patch_package_path"]).read_text(encoding="utf-8"))
    blocked_report = json.loads(Path(result["blocked_execution_report_path"]).read_text(encoding="utf-8"))
    task_tree = json.loads(Path(result["task_tree_path"]).read_text(encoding="utf-8"))

    assert result["status"] == "blocked"
    assert task_tree["boundary"]["track"] == "blocked_handoff"
    assert no_patch["artifact_type"] == "NoPatchPackage"
    assert no_patch["programmer_task_tree"]["role"] == "task_tree_builder"
    assert no_patch["patches"] == []
    assert no_patch["policy"]["patch_generation_allowed"] is False
    assert blocked_report["artifact_type"] == "BlockedExecutionReport"
    assert blocked_report["blocked_contract_rows"][0]["id"] == "CONTRACT-BLOCK-001"


def test_executable_acceptance_runner_fails_empty_obligations(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={"executable_acceptance": {"status": "empty", "obligations": []}},
        work_dir=tmp_path / "work",
    )

    assert result["artifact_type"] == "ExecutableAcceptanceResult"
    assert result["status"] == "failed"


def test_executable_acceptance_invokes_simple_python_target(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text(
        "def normalize_text(text: str) -> str:\n"
        "    if text is None:\n"
        "        raise ValueError('text required')\n"
        "    return text.strip().lower()\n",
        encoding="utf-8",
    )
    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "status": "ready",
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "main.py:normalize_text",
                        "kind": "positive_contract_case",
                        "given": {"text": " Sample "},
                        "expect": {"result": "string"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "contract_negative_missing_input",
                        "target": "main.py:normalize_text",
                        "kind": "malformed_input_case",
                        "given": {},
                        "expect": {"error": "controlled_validation_error"},
                        "oracle": "missing_required_input_rejected",
                    },
                    {
                        "id": "OBL-003",
                        "acceptance_id": "side_effect_boundary",
                        "target": "main.py:normalize_text",
                        "kind": "side_effect_scope_case",
                        "given": {"declared_scope": "writable_scope_only"},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ],
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["callable_harness_count"] == 1

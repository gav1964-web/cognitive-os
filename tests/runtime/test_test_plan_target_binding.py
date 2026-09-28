from runtime.test_plan_builder import build_test_plan


def test_executable_acceptance_uses_only_selected_target_criteria():
    plan = build_test_plan(
        technical_spec={
            "artifact_type": "TechnicalSpec",
            "acceptance_criteria": [
                {"id": "AC-001", "criterion": "Current contract", "source": "pkg/current.py:run"},
                {"id": "AC-002", "criterion": "Earlier architecture slice", "source": "pkg/old.py:build"},
                {"id": "AC-003", "criterion": "Global registry invariant"},
            ],
        },
        implementation_plan=_implementation_plan("pkg/current.py:run"),
    )

    executable = plan["executable_acceptance"]
    source_criteria = [row.get("source_criterion") for row in executable["obligations"]]
    assert "Current contract" in source_criteria
    assert "Earlier architecture slice" not in source_criteria
    assert "Global registry invariant" not in source_criteria
    assert executable["scope_binding"] == {
        "status": "target_bound",
        "target": "pkg/current.py:run",
        "selected_criteria": 1,
        "excluded_other_target_criteria": 1,
    }
    assert len(plan["acceptance_tests"]) == 3


def test_executable_acceptance_preserves_legacy_unscoped_criteria():
    plan = build_test_plan(
        technical_spec={
            "acceptance_criteria": [{"id": "AC-001", "criterion": "Returns normalized value"}],
        },
        implementation_plan=_implementation_plan("pkg/current.py:run"),
    )

    executable = plan["executable_acceptance"]
    assert executable["scope_binding"]["status"] == "legacy_unscoped"
    assert executable["obligations"][0]["source_criterion"] == "Returns normalized value"


def test_void_file_writer_uses_record_and_bounded_output_fixtures():
    target = "pkg/report.py:render"
    plan = build_test_plan(
        technical_spec={
            "acceptance_criteria": [
                {"id": "AC-001", "criterion": "Writes the report when data exists", "source": target},
            ],
        },
        implementation_plan={
            **_implementation_plan(target),
            "contract_binding": {
                "binding_status": "bound_to_extraction_contract",
                "input_contract": {"row": "ProtocolLike", "filename": "PathLike"},
                "output_contract": {"result": "VoidSideEffect"},
            },
        },
    )

    positive = plan["executable_acceptance"]["obligations"][0]
    assert positive["given"] == {
        "row": {"__fixture__": "record_row_empty"},
        "filename": "acceptance-output.tmp",
    }
    assert positive["expect"] == {"completed": True}
    assert positive["oracle"] == "call_completes_and_side_effect_boundary_is_declared"


def _implementation_plan(target: str) -> dict:
    return {
        "artifact_type": "ImplementationPlan",
        "implementation_target": {"candidate": target},
        "contract_binding": {
            "binding_status": "bound_to_extraction_contract",
            "input_contract": {"value": "str"},
            "output_contract": {"result": "str"},
        },
        "patch_scope": [target],
        "writable_scope": [target],
    }

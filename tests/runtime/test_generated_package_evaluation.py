from __future__ import annotations

from runtime.generated_package_evaluation import evaluate_generated_package


def test_generated_package_evaluation_scores_complete_sandbox_package():
    result = {
        "status": "sandbox_verified",
        "files": ["README.md", "src/demo/cli.py", "tests/test_cli.py"],
        "verification": {"status": "passed"},
        "implementation_plan": {
            "operation": {"operation": "demo", "profile": "stdin_text_expression", "evidence": ["demo"]},
            "operation_recipe": {
                "artifact_type": "OperationRecipe",
                "interface_contract": "stdin_to_stdout_text_transform",
                "transform": "uppercase",
            },
            "interface_contract": {"id": "stdin_to_stdout_text_transform"},
            "operation_graph": {"artifact_type": "SandboxOperationGraph"},
        },
        "source_code_changes": False,
        "registry_changes": False,
        "promotion_allowed": False,
        "llm_policy": {"llm_output_executed_directly": False},
    }

    report = evaluate_generated_package(
        prompt="напиши CLI",
        implementation_result=result,
        admission={"status": "passed"},
    )

    assert report["artifact_type"] == "GeneratedPackageEvaluation"
    assert report["status"] == "passed"
    assert report["score"] == 1.0
    assert report["failed_checks"] == []


def test_generated_package_evaluation_reports_evidence_gaps():
    report = evaluate_generated_package(prompt="", implementation_result={}, admission={"status": "failed"})

    assert report["status"] == "needs_review"
    assert "prompt_present" in report["failed_checks"]
    assert "sandbox_verified" in report["failed_checks"]
    assert report["score"] < 0.5

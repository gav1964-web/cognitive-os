import json
from pathlib import Path

from runtime.contract_rebind_request import build_contract_rebind_request
from runtime.programmer_executor import run_programmer_executor
from runtime.programmer_patch_strategy import build_patch_strategy


def test_contract_rebind_request_is_advisory_and_traces_candidates():
    request = build_contract_rebind_request(
        target="pkg/current.py:run",
        reason="test_plan_target_drift",
        alignment={"status": "target_drift", "candidate_targets": ["pkg/other.py:build"]},
        technical_spec={
            "extraction_contract": {
                "candidate": "pkg/current.py:run",
                "ranked_candidates": [{"source": "pkg/fallback.py:build"}],
            }
        },
        implementation_plan={"implementation_target": {"candidate": "pkg/current.py:run"}},
        test_plan={"status": "ready"},
    )

    assert request["artifact_type"] == "ContractRebindRequest"
    assert request["authority"] == "advisory_no_artifact_or_source_mutation"
    assert [row["target"] for row in request["candidate_targets"]] == [
        "pkg/other.py:build",
        "pkg/fallback.py:build",
        "pkg/current.py:run",
    ]
    assert "edit_source" in request["forbidden_actions"]


def test_executor_persists_contract_rebind_request_for_document_drift(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def run(value):\n    return value\n", encoding="utf-8")
    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec", "extraction_contract": {"candidate": "main.py:run"}},
        implementation_plan={
            "artifact_type": "ImplementationPlan",
            "implementation_target": {"candidate": "main.py:run"},
            "patch_intent": {"target_symbol": "main.py:run"},
            "writable_scope": ["main.py:run"],
            "expected_files": ["main.py"],
            "verification_commands": ["python -m compileall ."],
        },
        test_plan={
            "artifact_type": "TestPlan",
            "executable_acceptance": {
                "obligations": [{
                    "id": "OBL-001",
                    "target": "main.py:run",
                    "kind": "positive_contract_case",
                    "given": {"value": "sample"},
                    "expect": {"result": "str"},
                    "source_criterion": "`legacy.py:build` satisfies the selected extraction_contract shape.",
                }]
            },
        },
        run_verification=True,
    )

    request_path = Path(result["contract_rebind_request_path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["artifact_type"] == "ContractRebindRequest"
    assert request["candidate_targets"][0]["target"] == "legacy.py:build"
    assert result["reviewer_handoff"]["contract_rebind_request"] == request_path.as_posix()
    assert "return value" in (project / "main.py").read_text(encoding="utf-8")


def test_patch_strategy_detects_authoritative_source_criterion_drift(tmp_path: Path):
    proposal = _drift_proposal(
        tmp_path,
        "`pkg/other.py:build` satisfies the selected extraction_contract shape.",
    )

    assert proposal["contract_alignment"]["status"] == "target_drift"
    assert proposal["contract_alignment"]["reason"] == "authoritative_source_criterion_mismatch"
    assert proposal["contract_rebind_request"]["current_target"] == "pkg/current.py:run"
    assert proposal["contract_rebind_request"]["reason"] == "test_plan_acceptance_scope_drift"
    assert proposal["contract_rebind_request"]["requested_updates"][0] == "TechnicalSpec.acceptance_criteria"


def test_patch_strategy_keeps_single_context_reference_aligned(tmp_path: Path):
    proposal = _drift_proposal(tmp_path, "Preserve compatibility with helper `pkg/other.py:build`.")

    assert proposal["contract_alignment"]["status"] == "aligned"
    assert "contract_rebind_request" not in proposal


def _drift_proposal(tmp_path: Path, source_criterion: str) -> dict:
    return build_patch_strategy(
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "pkg/current.py:run"}},
        test_plan={
            "executable_acceptance": {
                "obligations": [{
                    "target": "pkg/current.py:run",
                    "source_criterion": source_criterion,
                }]
            }
        },
        synthesis={"status": "prepared", "reason": "required_input_guard_synthesized"},
        acceptance_summary={"signal_strength": "executable_callable"},
    )

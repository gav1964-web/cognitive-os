from __future__ import annotations

from pathlib import Path

from runtime.architecture_synthesis_policy import load_architecture_synthesis_policy
from runtime.project_architecture_synthesis import synthesize_project_architecture


ROOT = Path(__file__).resolve().parents[2]


def test_architecture_synthesis_policy_loads_current_catalog() -> None:
    policy = load_architecture_synthesis_policy(str(ROOT / "config" / "architecture_synthesis_policy.json"))

    assert policy["schema_version"] == "architecture_synthesis_policy.v1"
    assert policy["default_first_slice"]["target_task_types"]
    assert policy["bottlenecks"]["kind_order"]["hidden_orchestration"] == 0


def test_architecture_synthesis_uses_configured_task_focus_order(tmp_path: Path) -> None:
    synthesis = synthesize_project_architecture(
        _project_report(),
        level35_signals={"signals": []},
        level4_interpretation={"confidence": "medium"},
        analysis_tasks={
            "tasks": [
                {"type": "DEFINE_CHECKPOINT_POLICY", "target": "app.py:checkpoint", "acceptance": "checkpoint is explicit"},
                {"type": "DRAFT_PIPELINE_CAPABILITY", "target": "app.py:handle_request", "acceptance": "contract is explicit"},
            ]
        },
        root=tmp_path,
    )

    assert synthesis["task_focus"][0]["type"] == "DRAFT_PIPELINE_CAPABILITY"
    assert synthesis["verification_plan"][0].startswith("Create or extend focused tests")
    assert synthesis["what_not_to_touch_yet"][0].startswith("Do not rewrite the whole project")


def _project_report() -> dict:
    return {
        "summary": {"root": "project", "frameworks": ["FastAPI"], "routes": 1},
        "answers": {
            "1_scope": {"main_task": "Expose a small API", "domain_profile": {"kind": "web_framework_library", "confidence": 0.8, "evidence": ["FastAPI"]}},
            "2_execution": {
                "entrypoints": ["app.py"],
                "central_flow_nodes": [{"path": "app.py", "name": "handle_request", "call_count": 4}],
            },
            "3_capabilities": {
                "atomic_reusable_capabilities": ["app.py:normalize_name"],
                "too_broad_functions": [{"path": "app.py", "name": "handle_request", "loc": 90}],
            },
            "6_runtime_extraction_readiness": {
                "hidden_orchestrators": [{"path": "app.py", "name": "handle_request"}],
                "process_boundary_candidates": [{"target": "app.py:handle_request"}],
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [{"capability": "app.py:normalize_name", "reason": "bounded transform"}]
                },
            },
        },
    }

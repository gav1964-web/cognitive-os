import runtime.architect_first_slice_reselection as architect_reselection
import runtime.configured_role_pipeline as configured_pipeline
from runtime.architect_first_slice_reselection import reselect_architecture_first_slice
from runtime.first_slice_reselection_request import build_first_slice_reselection_request
from runtime.role_source_context import build_source_context
from runtime.spec_writer_target_binding import execution_cost_adjustment, promote_environment_ready_candidate
from runtime.technical_spec_builder import build_technical_spec






































def _ranked(source: str, score: int, status: str, *, semantic_score: int = 0) -> dict:
    return {
        "source": source,
        "score": score,
        "semantic_score": semantic_score,
        "index": 0 if status == "missing_external" else 1,
        "reasons": [],
        "evidence": {"dependency_readiness": {"status": status}},
    }


def _project_report(root, *, include_ready: bool) -> dict:
    pure = [{"path": "pkg/core.py", "name": "normalize"}] if include_ready else []
    return {
        "summary": {"root": root.as_posix()},
        "answers": {
            "3_capabilities": {"pure_transforms": pure},
            "6_runtime_extraction_readiness": {
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [{"capability": "pkg/adapter.py:convert_value"}]
                }
            },
        },
    }


def _architecture_decision(root, project_report: dict) -> dict:
    target = "pkg/adapter.py:convert_value"
    first_slice = {
        "name": "adapter_slice",
        "goal": "Specify one callable.",
        "targets": [target],
        "steps": ["Specify the callable contract."],
    }
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "status": "ok",
        "goal": "Prepare a safe first slice",
        "project": root.as_posix(),
        "chosen_option": {"id": "minimal_safe_extraction"},
        "first_slice_contract": first_slice,
        "source_context": build_source_context(
            project_root=root.as_posix(),
            project_report=project_report,
            sources=[target],
        ),
        "spec_writer_brief": {
            "scope": ["Specify one callable."],
            "files_or_symbols": [target],
            "acceptance_targets": ["Callable contract is explicit."],
            "first_slice": first_slice,
        },
        "traceability": [{"source": target, "requirement": "Capability requires TechnicalSpec."}],
    }

__all__ = [name for name in globals() if not name.startswith("__")]

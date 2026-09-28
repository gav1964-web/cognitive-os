"""Static dataflow checks for configured role workflows."""

from __future__ import annotations

from typing import Any


def workflow_dataflow_errors(stages: list[dict[str, Any]], initial_state: list[str]) -> list[str]:
    pending = {str(stage.get("stage_id") or ""): stage for stage in stages}
    available_by_stage: dict[str, set[str]] = {}
    initial = set(initial_state)
    errors = []
    while pending:
        ready = [
            (stage_id, stage)
            for stage_id, stage in pending.items()
            if set(stage.get("depends_on") or []) <= available_by_stage.keys()
        ]
        if not ready:
            errors.append(f"workflow_dependency_cycle:{','.join(pending)}")
            break
        for stage_id, stage in ready:
            dependencies = [str(item) for item in list(stage.get("depends_on") or [])]
            available = set(initial)
            for dependency in dependencies:
                available.update(available_by_stage[dependency])
            for required in [str(item) for item in list(stage.get("requires") or [])]:
                if required not in available:
                    errors.append(f"workflow_missing_input_provider:{stage_id}:{required}")
            available.update(str(item) for item in list(stage.get("provides") or []))
            available_by_stage[stage_id] = available
            del pending[stage_id]
    return errors

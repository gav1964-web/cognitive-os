"""Static registry of runtime handlers available to configured role workflows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def workflow_handler_registry() -> dict[str, Callable[[dict[str, Any]], None]]:
    from . import role_pipeline

    return {
        "role_pipeline.analyze": role_pipeline._stage_analyze,
        "role_pipeline.build": role_pipeline._stage_build,
        "role_pipeline.after_build": role_pipeline._stage_after_build,
        "role_pipeline.review": role_pipeline._stage_review,
        "role_pipeline.after_review": role_pipeline._stage_after_review,
        "role_pipeline.after_decision": role_pipeline._stage_after_decision,
        "role_pipeline.assemble_result": role_pipeline._stage_assemble_result,
        "role_pipeline.after_result": role_pipeline._stage_after_result,
    }

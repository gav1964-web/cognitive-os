"""Compatibility wrapper for project-analysis L3.5 signals and L4 deliberation."""

from __future__ import annotations

from typing import Any

from .local_inference import LocalInferenceConfig
from .project_deliberation import deliberate_project_report
from .project_signals import generate_project_signals
from .project_tasks import generate_project_tasks


def interpret_project_report(
    report: dict[str, Any],
    *,
    config: LocalInferenceConfig | None = None,
    signal_config: LocalInferenceConfig | None = None,
    cortex_config: LocalInferenceConfig | None = None,
    context_mode: str = "expanded",
) -> dict[str, Any]:
    level35_signals = generate_project_signals(report, config=signal_config or config)
    level4_interpretation = deliberate_project_report(
        report,
        level35_signals=level35_signals,
        config=cortex_config or config,
        context_mode=context_mode,
    )
    analysis_tasks = generate_project_tasks(
        level35_signals=level35_signals,
        level4_interpretation=level4_interpretation,
    )
    return {
        "level35_project_signals": level35_signals,
        "level4_project_interpretation": level4_interpretation,
        "analysis_tasks": analysis_tasks,
    }

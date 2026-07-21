"""Compatibility wrapper for project-analysis L3.5 signals and L4 deliberation."""

from __future__ import annotations

from typing import Any

from .local_inference import LocalInferenceConfig
from .project_architecture_synthesis import synthesize_project_architecture
from .project_deliberation import deliberate_project_report
from .research_loop import build_research_plan, project_research_gap_from_synthesis
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
    architecture_synthesis = synthesize_project_architecture(
        report,
        level35_signals=level35_signals,
        level4_interpretation=level4_interpretation,
        analysis_tasks=analysis_tasks,
    )
    knowledge_gap = project_research_gap_from_synthesis(architecture_synthesis)
    research_plan = build_research_plan(knowledge_gap) if knowledge_gap else None
    return {
        "level35_project_signals": level35_signals,
        "level4_project_interpretation": level4_interpretation,
        "analysis_tasks": analysis_tasks,
        "architecture_synthesis": architecture_synthesis,
        "knowledge_gap": knowledge_gap,
        "research_plan": research_plan,
    }

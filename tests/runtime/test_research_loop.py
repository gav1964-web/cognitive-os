from __future__ import annotations

from unittest.mock import patch

from runtime.research_loop import (
    build_knowledge_gap_packet,
    build_research_plan,
    execute_research_plan,
    project_research_gap_from_synthesis,
)


def test_research_plan_is_bounded_and_not_auto_executed():
    gap = build_knowledge_gap_packet(
        question="What architecture pattern fits a signing utility?",
        needed_for="architecture synthesis",
        role="architect",
        reason="generic python_project fallback",
    )

    plan = build_research_plan(gap)

    assert plan["artifact_type"] == "ResearchPlan"
    assert plan["policy"]["llm_may_not_browse_freely"] is True
    github_step = next(step for step in plan["steps"] if step["source_type"] == "github_repository_search")
    assert github_step["execute_by_default"] is False


def test_execute_research_plan_wraps_github_as_source_digest():
    gap = build_knowledge_gap_packet(
        question="python signing utility architecture",
        needed_for="architecture synthesis",
        role="architect",
        reason="unknown archetype",
        acceptable_sources=["github_repository_search"],
    )
    plan = build_research_plan(gap)
    fake = {
        "status": "ok",
        "knowledge_artifacts": [
            {
                "extracted_fact": "GitHub repository search returned candidates",
                "confidence": 0.6,
                "limitations": ["not ground truth"],
            }
        ],
    }
    with patch("runtime.research_loop.github_repository_knowledge", return_value=fake):
        result = execute_research_plan(gap, plan, github_limit=1)

    digest = result["source_digests"][0]
    assert result["status"] == "ok"
    assert digest["artifact_type"] == "SourceDigest"
    assert digest["confidence"] == 0.6
    assert "not ground truth" in digest["limitations"]


def test_project_research_gap_is_created_for_generic_synthesis():
    gap = project_research_gap_from_synthesis(
        {
            "project_profile": {"knowledge_rule": "python_project", "root": "itsdangerous"},
            "confidence": "medium",
        }
    )

    assert gap is not None
    assert gap["role"] == "architect"
    assert "python_project" in gap["reason"]

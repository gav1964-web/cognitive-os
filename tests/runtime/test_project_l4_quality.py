from runtime.project_l4_quality import score_l4_interpretation


def test_l4_quality_scores_grounded_interpretation():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "HTTPX is a Python HTTP client library.",
            "capability_decomposition": ["HTTP request handling via httpx/_api.py:get"],
            "refactor_plan": ["Split broad URL parsing in httpx/_urlparse.py:urlparse"],
            "open_questions": ["Which retry policy should be explicit?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "HTTPX is a Python HTTP client library.",
                "entrypoints": ["httpx/_api.py"],
                "capabilities": ["HTTP request handling"],
                "hotspots": [{"target": "httpx/_urlparse.py:urlparse"}],
            },
        }
    )

    assert result["passed"] is True
    assert result["quality_score"] >= 0.9
    assert result["warnings"] == []


def test_l4_quality_rejects_context_only_capability():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "orjson is a JSON library.",
            "capability_decomposition": ["JSON loading benchmark in bench/benchmark_loads.py"],
            "refactor_plan": ["Define dependency risk quarantine policy"],
            "open_questions": ["Which runtime boundary is product-level?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "orjson is a fast JSON library.",
                "risks": ["unpinned_dependencies"],
            },
        }
    )

    assert result["passed"] is False
    assert "capability_grounding" in result["warnings"]


def test_l4_quality_rejects_self_referential_summary():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "Level 4 turns deterministic facts into human-readable output.",
            "capability_decomposition": ["HTTP request handling"],
            "refactor_plan": ["Split HTTP request handling"],
            "open_questions": [],
            "confidence": "high",
            "fact_summary": {"task": "HTTP request handling", "capabilities": ["HTTP request handling"]},
        }
    )

    assert result["passed"] is False
    assert "summary_grounding" in result["warnings"]
    assert "uncertainty_honesty" in result["warnings"]

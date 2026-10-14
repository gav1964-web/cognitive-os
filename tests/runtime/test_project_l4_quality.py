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


def test_l4_quality_rejects_plausible_placeholder_identifiers_and_vague_refactor():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "fastapi uvicorn pydantic>=2 PyYAML pytest pytest-asyncio.",
            "capability_decomposition": ["Data processing via Schema Z", "Core functionality derived from Class W"],
            "refactor_plan": ["Extract logic from main.py to separate modules"],
            "open_questions": ["What specific optimizations can be applied?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "Expose an HTTP API service and return structured JSON responses.",
                "entrypoints": ["app/api/server.py"],
                "capabilities": ["app/api/server.py:provider_error_handler"],
                "schemas": ["app/api/schemas.py:ChatRequest"],
            },
        }
    )

    assert result["passed"] is False
    assert result["scores"]["summary_grounding"] == 0.0
    assert result["scores"]["capability_grounding"] == 0.0
    assert result["scores"]["actionability"] == 0.0


def test_l4_quality_rejects_bracketed_template_content():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "Target project provides [specific functionality].",
            "capability_decomposition": ["[Feature A] via [core function]"],
            "refactor_plan": ["Review hotspot app.py:index"],
            "open_questions": ["Does [component] need documentation?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "Render an incident map.",
                "entrypoints": ["app.py"],
                "capabilities": ["app.py:index"],
                "hotspots": [{"target": "app.py:index"}],
            },
        }
    )

    assert result["passed"] is False
    assert "template_placeholder" in result["warnings"]


def test_l4_quality_accepts_http_method_brackets_but_rejects_unanchored_action():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "The service handles chat completion requests.",
            "capability_decomposition": ["Chat handling through app/api/server.py:_handle_chat_request"],
            "refactor_plan": ["Move encryption constants from the main package into config"],
            "cognitive_loop": "call route ['POST'] /v1/chat/completions; capture response",
            "open_questions": ["Which provider failures should be retried?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "The service handles chat completion requests.",
                "entrypoints": ["app/api/server.py"],
                "capabilities": ["app/api/server.py:_handle_chat_request"],
                "hotspots": [{"target": "app/api/server.py:_handle_chat_request"}],
            },
        }
    )

    assert "template_placeholder" not in result["warnings"]
    assert result["scores"]["actionability"] == 0.0


def test_l4_quality_rejects_open_question_with_unknown_source_path():
    result = score_l4_interpretation(
        {
            "source": "external_l4",
            "executive_summary": "The API routes requests to configured providers.",
            "capability_decomposition": ["Provider routing via app/api/server.py:_handle_chat_request"],
            "refactor_plan": ["Split app/api/server.py:_handle_chat_request by provider policy"],
            "open_questions": ["Does lib/grpc_client.go support every protocol?"],
            "confidence": "medium",
            "fact_summary": {
                "task": "The API routes requests to configured providers.",
                "entrypoints": ["app/api/server.py"],
                "capabilities": ["app/api/server.py:_handle_chat_request"],
                "hotspots": [{"target": "app/api/server.py:_handle_chat_request"}],
            },
        }
    )

    assert result["passed"] is False
    assert "ungrounded_open_question" in result["warnings"]

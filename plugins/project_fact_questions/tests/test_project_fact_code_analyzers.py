from plugins.project_fact_questions.src.main import run


def test_project_fact_questions_answers_gigachat_auto_model_selection(tmp_path):
    (tmp_path / "app" / "gigachat").mkdir(parents=True)
    (tmp_path / "app" / "gigachat" / "orchestrator.py").write_text(
        "\n".join(
            [
                "selected_model = model",
                "if selected_model is None:",
                "    selected_model, search_flag, search_queries = await self.classifier.classify(messages)",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "providers.yaml").write_text(
        'available_models:\n  - "GigaChat"\n  - "GigaChat-Pro"\n',
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [
                    {"path": "app/gigachat/orchestrator.py", "line_count": 3},
                    {"path": "config/providers.yaml", "line_count": 3},
                ],
            },
            "python_structure": {
                "root": str(tmp_path),
                "files": [{"path": "app/gigachat/orchestrator.py", "imports": [], "functions": []}],
            },
            "questions": ["есть ли автоматический выбор модели при вызове провайдера GigaChat"],
        }
    )

    answer = result["answers"]["gigachat_model_auto_selection"]
    assert answer["status"] == "found"
    assert answer["answer"] == "yes"
    assert any(row["path"] == "app/gigachat/orchestrator.py" for row in answer["evidence"])


def test_project_fact_questions_does_not_report_gigachat_auto_selection_for_default_model(tmp_path):
    (tmp_path / "app" / "gigachat").mkdir(parents=True)
    (tmp_path / "app" / "gigachat" / "orchestrator.py").write_text(
        "\n".join(
            [
                "selected_model = model",
                "if selected_model is None:",
                "    selected_model = \"GigaChat\"",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [{"path": "app/gigachat/orchestrator.py", "line_count": 3}],
            },
            "python_structure": {
                "root": str(tmp_path),
                "files": [{"path": "app/gigachat/orchestrator.py", "imports": [], "functions": []}],
            },
            "questions": ["есть ли автоматический выбор модели при вызове провайдера GigaChat"],
        }
    )

    answer = result["answers"]["gigachat_model_auto_selection"]
    assert answer["status"] == "not_found"


def test_project_fact_questions_answers_llm_cache_exists(tmp_path):
    (tmp_path / "app" / "core").mkdir(parents=True)
    (tmp_path / "app" / "providers").mkdir(parents=True)
    (tmp_path / "app" / "core" / "cache.py").write_text(
        "\n".join(
            [
                "class LLMCache:",
                "    def build_key(self): pass",
                "    async def get_cached_response(self, key): pass",
                "    async def store_response(self, key, text): pass",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "app" / "providers" / "factory.py").write_text(
        "\n".join(
            [
                "cache_backend = JsonFileCacheBackend(cache_file)",
                "cache = LLMCache(cache_backend)",
                "provider_caches[provider_id] = cache",
                "cache=provider_caches.get(provider_id)",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [
                    {"path": "app/core/cache.py", "line_count": 4},
                    {"path": "app/providers/factory.py", "line_count": 4},
                ],
            },
            "python_structure": {
                "root": str(tmp_path),
                "files": [
                    {"path": "app/core/cache.py", "imports": [], "functions": []},
                    {"path": "app/providers/factory.py", "imports": [], "functions": []},
                ],
            },
            "questions": ["существует ли кэш обращений к LLM"],
        }
    )

    answer = result["answers"]["llm_cache_exists"]
    assert answer["status"] == "found"
    assert answer["answer"] == "yes"
    assert any(row["path"] == "app/core/cache.py" for row in answer["evidence"])
    assert result["selected_answers"][0]["answer_key"] == "llm_cache_exists"


def test_project_fact_questions_answers_llm_cache_sharing(tmp_path):
    (tmp_path / "app" / "core").mkdir(parents=True)
    (tmp_path / "app" / "providers").mkdir(parents=True)
    (tmp_path / "app" / "core" / "cache.py").write_text(
        "\n".join(
            [
                "class LLMCache:",
                "    cache_input = {",
                "        \"provider\": provider_id,",
                "        \"model\": model_name,",
                "    }",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "app" / "providers" / "factory.py").write_text(
        "\n".join(
            [
                "def _provider_cache_file(provider_id: str) -> str:",
                "    return f\"llm_cache_{provider_id}.json\"",
                "provider_caches[provider_id] = cache",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [
                    {"path": "app/core/cache.py", "line_count": 5},
                    {"path": "app/providers/factory.py", "line_count": 3},
                ],
            },
            "python_structure": {"root": str(tmp_path), "files": []},
            "questions": ["для разных LLM используется один и тот же кэш?"],
        }
    )

    answer = result["answers"]["llm_cache_sharing"]
    assert answer["status"] == "found"
    assert answer["answer"] == "separate_per_provider_and_model_keyed"
    assert any(row["path"] == "app/providers/factory.py" for row in answer["evidence"])
    assert result["selected_answers"][0]["answer_key"] == "llm_cache_sharing"


def test_project_fact_questions_recommends_keeping_provider_and_model_in_cache_key(tmp_path):
    (tmp_path / "app" / "core").mkdir(parents=True)
    (tmp_path / "app" / "providers").mkdir(parents=True)
    (tmp_path / "app" / "core" / "cache.py").write_text(
        "\n".join(
            [
                "class LLMCache:",
                "    cache_input = {",
                "        \"provider\": provider_id,",
                "        \"model\": model_name,",
                "    }",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "app" / "providers" / "factory.py").write_text(
        "\n".join(
            [
                "def _provider_cache_file(provider_id: str) -> str:",
                "    return f\"llm_cache_{provider_id}.json\"",
                "provider_caches[provider_id] = cache",
            ]
        ),
        encoding="utf-8",
    )

    result = run(
        {
            "tree": {
                "root": str(tmp_path),
                "files": [
                    {"path": "app/core/cache.py", "line_count": 5},
                    {"path": "app/providers/factory.py", "line_count": 3},
                ],
            },
            "python_structure": {"root": str(tmp_path), "files": []},
            "questions": ["имеет ли смысл убрать из кэша признаки модели и провайдера"],
        }
    )

    answer = result["answers"]["llm_cache_key_recommendation"]
    assert answer["status"] == "found"
    assert answer["answer"] == "do_not_remove_provider_or_model_from_cache_key"
    assert "ложные cache hit" in answer["recommendation"]
    assert result["selected_answers"][0]["answer_key"] == "llm_cache_key_recommendation"

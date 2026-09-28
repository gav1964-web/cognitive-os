"""Product-level quality gate for generated projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any


READY_THRESHOLD = 0.92


def evaluate_generated_product(report: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(str(report.get("project_dir") or ""))
    source = dict(report.get("source_code", {}))
    files = [str(item) for item in source.get("files", [])]
    tester = dict(report.get("tester_review", {}))
    verification = dict(report.get("verification_report", {}))
    decision = dict(report.get("release_decision", {}))
    text = _read_texts(project_dir, files)
    source_text = "\n".join(value for key, value in text.items() if key.startswith("src/") and key.endswith(".py"))
    test_text = "\n".join(value for key, value in text.items() if key.startswith("tests/") and key.endswith(".py"))
    readme = text.get("README.md", "")
    case_name = str(dict(tester.get("review_target", {})).get("case") or "")
    checks = {
        "project_directory_present": project_dir.is_dir(),
        "source_files_present": any(item.startswith("src/") and item.endswith(".py") for item in files),
        "tests_present": any(item.startswith("tests/") and item.endswith(".py") for item in files),
        "readme_present": "README.md" in files and bool(readme.strip()),
        "project_scoped_tests_pass": verification.get("status") == "passed"
        and verification.get("project_scoped") is True,
        "release_decision_positive": decision.get("decision") in {"release_ready", "release_ready_with_risks"},
        "cli_or_service_entrypoint": _has_cli_or_service_entrypoint(source_text, files),
        "input_output_contract_visible": bool(dict(tester.get("checks", {})).get("cli_accepts_input_output"))
        or "FastAPI(" in source_text,
        "controlled_error_path": _has_controlled_error_path(source_text, test_text),
        "readme_has_run_and_test_commands": "pytest" in readme.lower()
        and ("python -m" in readme.lower() or "uvicorn" in readme.lower()),
        "no_generated_runtime_cache_files": not _has_runtime_cache_files(project_dir),
    }
    checks.update(_case_specific_checks(case_name, files, text, source_text, test_text, readme))
    failed = [name for name, ok in checks.items() if not ok]
    score = round(sum(1 for ok in checks.values() if ok) / len(checks), 3)
    return {
        "artifact_type": "GeneratedProductQuality",
        "status": "passed" if score >= READY_THRESHOLD and not failed else "needs_rework",
        "score": score,
        "ready_threshold": READY_THRESHOLD,
        "checks": checks,
        "failed_checks": failed,
        "verdict": _verdict(score, failed),
    }


def _case_specific_checks(
    case_name: str,
    files: list[str],
    text: dict[str, str],
    source_text: str,
    test_text: str,
    readme: str,
) -> dict[str, bool]:
    if case_name == "news_site_scraper_cli":
        corpus = "\n".join(text.values())
        return {
            "news_scraper_supports_markdown_output": "write_news_markdown" in source_text
            and "suffix == '.md'" in source_text,
            "news_scraper_enforces_top10": "min(args.top, 10)" in source_text
            or "min(per_site_top, 10)" in source_text,
            "news_scraper_has_site_profile": "profile_for" in source_text
            and "SiteProfile" in source_text,
            "news_scraper_site_profile_is_contract": "article_path_patterns" in source_text
            and "blocked_path_markers" in source_text
            and "blocked_titles" in source_text
            and "test_site_profile_contains_article_contract" in test_text,
            "news_scraper_has_generic_discovery": "_looks_like_news_candidate" in source_text
            and "test_parser_discovers_news_candidates_on_unknown_site_without_profile" in test_text,
            "news_scraper_rejects_navigation_noise": "Newsletters" in test_text
            and "See all reviews" in test_text
            and "Все обзоры" in test_text
            and "test_parser_ignores_common_navigation_cards" in test_text,
            "news_scraper_has_feed_discovery": "discover_feed_urls" in source_text
            and "parse_feed_items" in source_text
            and "_fetch_feed" in source_text
            and "timeout=3.0" in source_text
            and "test_feed_discovery_finds_declared_and_common_feeds" in test_text
            and "test_cli_uses_feed_fallback_when_front_page_has_no_news" in test_text,
            "news_scraper_has_json_ld_extraction": "_parse_json_ld_news" in source_text
            and "newsarticle" in source_text
            and "test_parser_extracts_schema_org_json_ld_news_articles" in test_text,
            "news_scraper_has_sitemap_discovery": "discover_sitemap_urls" in source_text
            and "rows_from_sitemap" in source_text
            and "test_sitemap_discovery_and_parser_keep_article_like_same_host_urls" in test_text,
            "news_scraper_has_strategy_registry": "STRATEGY_REGISTRY" in source_text
            and "html_links" in source_text
            and "json_ld" in source_text
            and "rss_atom" in source_text
            and "sitemap" in source_text
            and "browser_dom" in source_text
            and "api_probe" in source_text
            and "test_strategy_registry_lists_allowed_extraction_strategies" in test_text,
            "news_scraper_feed_fallback_is_budgeted": "total_timeout" in source_text
            and "time.monotonic" in source_text
            and "test_feed_fallback_uses_short_timeout_budget" in test_text,
            "news_scraper_has_llm_fallback_after_deterministic_failure": "extract_news_with_llm" in source_text
            and "diagnose_extraction_failure" in source_text
            and "execute_strategy_candidate" in source_text
            and "SiteDiagnosis" in source_text
            and "StrategyCandidate" in source_text
            and "feed_candidate" in source_text
            and "json_candidate" in source_text
            and "DEFAULT_MODEL = 'deepseek/deepseek-chat'" in source_text
            and "attempting LLM fallback" in source_text
            and "--no-llm-fallback" in source_text
            and "test_cli_uses_llm_fallback_after_html_and_feed_fail" in test_text
            and "test_llm_extractor_normalizes_and_filters_model_rows" in test_text,
            "news_scraper_executes_diagnosed_strategies_safely": "test_strategy_executor_runs_feed_candidate_with_validated_urls" in test_text
            and "test_strategy_executor_runs_json_candidate_through_same_validator" in test_text
            and "_candidate_urls" in source_text
            and "_parse_feed_xml" in source_text,
            "news_scraper_has_browser_required_contract": "fetch_rendered_html" in source_text
            and "browser_required" in source_text
            and "--browser" in source_text
            and "browser = [\"playwright" in corpus
            and "test_cli_uses_browser_fallback_when_l45_diagnoses_browser_required" in test_text,
            "news_scraper_has_explicit_browser_modes": "choices=('auto', 'always', 'off')" in source_text
            and "--browser-timeout-ms" in source_text
            and "test_cli_supports_explicit_browser_always_mode_before_llm" in test_text
            and "test_cli_respects_browser_off_when_l45_diagnoses_browser_required" in test_text,
            "news_scraper_has_deterministic_browser_challenge_detection": "_looks_browser_required" in source_text
            and "_local_browser_required_diagnosis" in source_text
            and "test_cli_detects_browser_required_shell_before_model" in test_text,
            "news_scraper_skips_feed_probe_for_browser_challenges": "browser_shell" in source_text
            and "not browser_shell" in source_text
            and "test_cli_skips_feed_probe_for_browser_challenge_shell" in test_text,
            "news_scraper_avoids_duplicate_browser_attempts": "browser_attempted" in source_text
            and "test_cli_does_not_call_browser_twice_when_always_then_l45_browser_required" in test_text,
            "news_scraper_writes_controlled_failure_report": "NewsExtractionFailureReport" in source_text
            and "write_failure_report" in source_text
            and "test_cli_writes_failure_report_when_l45_strategy_cannot_be_executed" in test_text
            and "test_cli_writes_failure_report_for_browser_only_failure" in test_text,
            "news_scraper_fixture_is_explicitly_not_live": "Fixture parser smoke output, not live site news." in corpus
            and "Fixtures are parser smoke evidence only" in corpus,
            "news_scraper_uses_news_like_fixture": "Тестовая fixture-новость 01" in corpus
            and "Тестовая fixture-новость 10" in corpus,
            "news_scraper_fixture_has_ten_items": corpus.count("<article>") >= 10
            and "](https://ixbt.com/news/fixture/" in test_text,
            "news_scraper_live_empty_page_blocks": "no news items parsed from live URL" in source_text
            and "test_cli_returns_controlled_error_when_live_page_has_no_news" in test_text,
            "news_scraper_live_top_count_is_contract": "parsed only {len(rows)} news items" in source_text
            and "test_cli_returns_controlled_error_when_live_page_has_too_few_news" in test_text,
            "news_scraper_live_summary_enrichment": "enrich_missing_summaries" in source_text
            and "extract_article_summary" in source_text
            and "test_cli_enriches_live_summaries" in test_text,
            "news_scraper_has_per_article_summary": "summary" in source_text
            and "Производитель раскрыл характеристики новой беззеркальной камеры. В новости перечислены режимы съемки" in corpus
            and "Публикация связывает устройство с ближайшей презентацией бренда." in corpus,
            "news_scraper_has_no_placeholder_news": "Example 3DNews item" not in corpus
            and "Fallback technology news item" not in corpus,
            "news_scraper_supports_multi_site_merge_summary": "--also-input" in source_text
            and "_collect_rows_from_input" in source_text
            and "_combined_summary" in source_text
            and "test_cli_collects_multiple_sites_then_dedupes_and_writes_one_summary" in test_text,
            "news_scraper_has_multi_site_scaling_controls": "--top-per-site" in source_text
            and "--total-top" in source_text
            and "--max-sites" in source_text
            and "--site-timeout" in source_text
            and "--total-timeout" in source_text
            and "--fail-policy" in source_text
            and "--dedupe" in source_text
            and "--workers" in source_text
            and "NewsCollectionPlan" in source_text
            and "test_cli_limits_total_top_and_max_sites" in test_text
            and "test_cli_strict_fail_policy_stops_on_failed_site" in test_text
            and "test_merge_rows_supports_canonical_url_dedupe" in test_text,
            "news_scraper_has_grounded_llm_summary_stage": "--summary-mode" in source_text
            and "summarize_rows_with_llm" in source_text
            and "Используй только поля title, source, url и summary" in source_text
            and "одно общее резюме на русском языке" in source_text
            and "не разбивку по сайтам" in source_text
            and "повторная попытка" in source_text
            and "никогда не пиши Summary unavailable" in source_text
            and "test_cli_uses_llm_summary_after_rows_are_collected" in test_text,
            "news_scraper_outputs_russian_single_aggregate_markdown_summary": "# Сводка новостей" in source_text
            and "## Общее резюме" in source_text
            and "## Ссылки для проверки" in source_text
            and "Summary unavailable: article text was not extracted." not in source_text
            and "test_markdown_report_has_one_russian_overall_summary_and_no_per_article_placeholder" in test_text,
            "news_scraper_has_bounded_parallel_collection": "ThreadPoolExecutor" in source_text
            and "as_completed" in source_text
            and "test_cli_workers_process_multiple_sites" in test_text,
            "news_scraper_uses_external_site_profile_kb": any(item.endswith("news_site_profiles.json") for item in files)
            and "_load_profiles" in source_text
            and "test_site_profile_is_loaded_from_json_data_file" in test_text,
            "news_scraper_writes_news_run_report": "NewsRunReport" in source_text
            and "--run-report" in source_text
            and "test_cli_writes_news_run_report" in test_text,
            "news_scraper_has_llm_site_profile_proposal": "SiteProfileProposal" in source_text
            and "--profile-proposal" in source_text
            and "candidate_not_applied_automatically" in source_text
            and "test_profile_proposal_is_candidate_not_auto_applied" in test_text
            and "test_cli_writes_profile_proposal_on_strict_failure" in test_text,
            "news_scraper_has_profile_promotion_gate": "ProfilePromotionDecision" in source_text
            and "--promote-profile-proposal" in source_text
            and "profile_not_written_to_kb" in source_text
            and "test_profile_promotion_gate_promotes_valid_candidate_with_evidence" in test_text
            and "test_cli_runs_profile_promotion_gate" in test_text,
            "news_scraper_has_approved_kb_patch_flow": "KBPatchProposal" in source_text
            and "KBPatchApplyResult" in source_text
            and "--kb-patch-proposal" in source_text
            and "--apply-approved-profile" in source_text
            and "requires_human_approval" in source_text
            and "test_kb_patch_proposal_requires_human_approval" in test_text
            and "test_cli_applies_only_approved_profile_patch" in test_text,
            "news_scraper_has_docker_cli_contract": "Dockerfile" in files
            and "ENTRYPOINT [\"python\", \"-m\", \"news_site_scraper.cli\"]" in text.get("Dockerfile", "")
            and "docker build" in readme.lower()
            and "docker run" in readme.lower()
            and "test_popular_sites_contract_and_dockerfile_exist" in test_text,
            "news_scraper_has_windows_batch_launcher": "run_news_scraper.bat" in files
            and "PYTHONPATH=%ROOT%src" in text.get("run_news_scraper.bat", "")
            and "python -m news_site_scraper.cli" in text.get("run_news_scraper.bat", "")
            and "Windows launcher" in readme
            and "run_news_scraper.bat" in test_text,
            "news_scraper_has_external_popular_sites_seed": any(item.endswith("popular_news_sites.json") for item in files)
            and "\"sites\"" in text.get("src/news_site_scraper/popular_news_sites.json", "")
            and text.get("src/news_site_scraper/popular_news_sites.json", "").count("\"url\"") >= 10
            and "load_seed_sites" in source_text
            and "--use-popular-sites" in source_text,
            "news_scraper_discovers_popular_sources_from_topic": any(item.endswith("source_discovery.py") for item in files)
            and "discover_news_sources" in source_text
            and "--source-discovery" in source_text
            and "source discovery returned no news sources" in source_text
            and "test_source_discovery_extracts_top_news_sources_from_search_results" in test_text
            and "test_popular_sites_search_mode_fails_when_sources_cannot_be_discovered" in test_text,
            "news_scraper_has_llm_assisted_source_discovery": "discover_news_sources_with_llm" in source_text
            and "--source-llm-mode" in source_text
            and "--llm-base-url" in source_text
            and "--llm-model" in source_text
            and "LLM proposed" in source_text
            and "test_llm_source_discovery_validates_model_sources" in test_text
            and "test_llm_source_discovery_recovers_urls_from_non_json_model_text" in test_text
            and "test_cli_uses_llm_source_discovery_when_search_html_has_no_sources" in test_text,
            "news_scraper_has_topic_query_contract": "--topic" in source_text
            and "--query" in source_text
            and "_filter_rows_by_topic" in source_text
            and "_topic_token_matches" in source_text
            and "no collected news items matched topic" in source_text
            and "test_cli_popular_sites_mode_discovers_sources_filters_topic_and_writes_single_md_summary" in test_text,
            "news_scraper_topic_mode_uses_search_article_fallback": "discover_news_article_rows" in source_text
            and "_topic_search_rows" in source_text
            and "topic article discovery returned" in source_text
            and "test_popular_topic_mode_falls_back_to_search_article_rows_when_homepages_miss_topic" in test_text,
            "news_scraper_popular_topic_mode_writes_single_markdown_report": "popular-sites topic mode writes one Markdown report" in source_text
            and "test_popular_sites_mode_requires_markdown_output" in test_text
            and "Popular-sites example" in readme
            and "Общее резюме" in test_text,
        }
    if case_name == "web_research_summarizer_fastapi":
        return {
            "web_research_fastapi_has_research_endpoint": "FastAPI(" in source_text
            and "@app.post('/research')" in source_text
            and "TestClient" in test_text,
            "web_research_fastapi_enforces_top_20": "le=20" in source_text
            and "min(max(top, 1), 20)" in source_text,
            "web_research_fastapi_uses_gigachat_gateway": "DEFAULT_BASE_URL = 'http://127.0.0.1:8000/v1'" in source_text
            and "DEFAULT_MODEL = 'GigaChat'" in source_text
            and "/chat/completions" in source_text,
            "web_research_fastapi_has_adapter_boundaries": "search_fn" in source_text
            and "fetch_fn" in source_text
            and "summary_fn" in source_text,
            "web_research_fastapi_has_offline_mocks": "fake_search" in test_text
            and "fake_fetch" in test_text
            and "fake_summary" in test_text
            and "fake_urlopen" in test_text,
            "web_research_fastapi_documents_env": "LLM_BASE_URL" in readme
            and "LLM_MODEL" in readme
            and "WEB_SEARCH_ENDPOINT_TEMPLATE" in readme,
        }
    if case_name != "web_research_summarizer_cli":
        return {}
    return {
        "web_research_enforces_top_15": "min(args.top, 15)" in source_text or "[:limit]" in source_text,
        "web_research_has_live_search_adapter": "search_endpoint_template" in source_text
        and "urlopen" in source_text,
        "web_research_has_default_plain_query_search": "search_duckduckgo_html" in source_text
        and "parse_duckduckgo_html" in source_text,
        "web_research_has_offline_fixtures": "tests/fixtures/search_results.json" in files
        and "--fixture-search" in source_text,
        "web_research_outputs_markdown_and_json": "target.suffix.lower() == '.json'" in source_text
        and "# Web Research Summary" in source_text,
        "web_research_outputs_single_summary_report": "## Summary" in source_text
        and "_combined_summary" in source_text
        and "## {index}" not in source_text,
        "web_research_keeps_source_links": "## Sources" in source_text and "url" in source_text,
        "web_research_handles_empty_or_malformed_input": "malformed" in test_text.lower()
        and ("empty" in test_text.lower() or "empty_article_text" in source_text),
        "web_research_documents_network_policy": "live network" in readme.lower()
        and "--search-endpoint-template" in readme,
    }


def _has_cli_or_service_entrypoint(source_text: str, files: list[str]) -> bool:
    return "FastAPI(" in source_text or any(item.endswith("/cli.py") for item in files)


def _has_controlled_error_path(source_text: str, test_text: str) -> bool:
    markers = ["raise SystemExit", "ValueError", "HTTPException", "FileNotFoundError"]
    edge_markers = ["missing", "malformed", "invalid", "unsupported", "empty", "requires", "reject"]
    return any(marker in source_text for marker in markers) and any(marker in test_text.lower() for marker in edge_markers)


def _has_runtime_cache_files(project_dir: Path) -> bool:
    if not project_dir.is_dir():
        return True
    for path in project_dir.rglob("*"):
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} or ".pytest_cache" in path.parts:
            return True
    return False


def _read_texts(project_dir: Path, files: list[str]) -> dict[str, str]:
    if not project_dir.is_dir():
        return {}
    root = project_dir.resolve()
    texts: dict[str, str] = {}
    for item in files:
        path = (root / item).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.name != "Dockerfile" and path.suffix.lower() not in {".py", ".md", ".toml", ".json", ".html", ".csv", ".txt", ".bat"}:
            continue
        if path.is_file():
            texts[item] = path.read_text(encoding="utf-8", errors="replace")
    return texts


def _verdict(score: float, failed: list[str]) -> str:
    if score >= READY_THRESHOLD and not failed:
        return "generated project is usable as a bounded product package"
    return "generated project needs product-level rework before it should be treated as ready"

from __future__ import annotations

from plugins.project_map_report.src.extraction_ranking import add_extraction_candidate, extraction_candidate_sort_key


def test_extraction_ranking_prioritizes_bounded_policy_before_broad_flow():
    candidates = {}
    add_extraction_candidate(
        candidates,
        {"path": "pkg/runtime.py", "name": "run_workflow", "loc": 160, "call_count": 24},
        "core_flow",
        "central flow",
    )
    add_extraction_candidate(
        candidates,
        {"path": "pkg/policy.py", "name": "can_process", "loc": 20, "call_count": 2},
        "bounded_policy",
        "reproducible boolean policy decision",
    )

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] == "pkg/policy.py:can_process"


def test_extraction_ranking_demotes_low_value_first_slice_helpers():
    candidates = {}
    for item in [
        {"path": "pkg/worker/base.py", "name": "__init__", "loc": 120, "call_count": 12},
        {"path": "pkg/__init__.py", "name": "configure_logging", "loc": 80, "call_count": 8},
        {"path": "pkg/queries.py", "name": "all", "loc": 30, "call_count": 6},
        {"path": "pkg/providers/factory.py", "name": "build_providers_from_config", "loc": 70, "call_count": 4},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] == "pkg/providers/factory.py:build_providers_from_config"
    assert ranked[-1]["capability"] in {"pkg/worker/base.py:__init__", "pkg/__init__.py:configure_logging"}


def test_extraction_ranking_prefers_query_contract_over_write_operation():
    candidates = {}
    for item in [
        {"path": "tinydb/storages.py", "name": "write", "loc": 20, "call_count": 9},
        {"path": "tinydb/table.py", "name": "search", "loc": 43, "call_count": 8},
        {"path": "tinydb/table.py", "name": "update", "loc": 103, "call_count": 11},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] == "tinydb/table.py:search"
    assert ranked[-1]["capability"] in {"tinydb/storages.py:write", "tinydb/table.py:update"}


def test_extraction_ranking_prefers_database_query_shape_over_generic_accessor():
    candidates = {}
    for item in [
        {"path": "tinydb/table.py", "name": "get", "loc": 80, "call_count": 12},
        {"path": "tinydb/queries.py", "name": "_generate_test", "loc": 42, "call_count": 4},
        {"path": "tinydb/table.py", "name": "search", "loc": 43, "call_count": 8},
        {"path": "tinydb/middlewares.py", "name": "read", "loc": 36, "call_count": 7},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] == "tinydb/table.py:search"
    assert ranked[-1]["capability"] in {"tinydb/table.py:get", "tinydb/middlewares.py:read"}


def test_extraction_ranking_demotes_vendored_helpers():
    candidates = {}
    for item in [
        {"path": "external-deps/python-lsp-server/pylsp/plugins/symbols.py", "name": "pylsp_document_symbols", "loc": 120, "call_count": 12},
        {"path": "spyder/plugins/editor/plugin.py", "name": "handle_lsp_response", "loc": 80, "call_count": 8},
        {"path": "spyder/plugins/preferences/widgets.py", "name": "create_widget", "loc": 70, "call_count": 4},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] in {
        "spyder/plugins/editor/plugin.py:handle_lsp_response",
        "spyder/plugins/preferences/widgets.py:create_widget",
    }
    assert ranked[-1]["capability"] == "external-deps/python-lsp-server/pylsp/plugins/symbols.py:pylsp_document_symbols"


def test_extraction_ranking_prefers_domain_contract_targets():
    candidates = {}
    for item in [
        {"path": "airflow/api/common/trigger_dag.py", "name": "_trigger_dag", "loc": 50, "call_count": 5},
        {"path": "airflow/utils/helpers.py", "name": "validate_key", "loc": 90, "call_count": 12},
        {"path": "airflow/configuration.py", "name": "get", "loc": 80, "call_count": 20},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] == "airflow/api/common/trigger_dag.py:_trigger_dag"


def test_extraction_ranking_prefers_config_provider_and_classifier_over_lifecycle_wrappers():
    candidates = {}
    for item in [
        {"path": "app/api/server.py", "name": "lifespan", "loc": 160, "call_count": 24},
        {"path": "app/api/server.py", "name": "_ensure_local_llm_provider", "loc": 120, "call_count": 18},
        {"path": "app/api/routing.py", "name": "resolve_openai_route", "loc": 110, "call_count": 16},
        {"path": "app/core/config.py", "name": "load_config", "loc": 70, "call_count": 5},
        {"path": "app/providers/adapters.py", "name": "generate_result", "loc": 80, "call_count": 5},
        {"path": "app/gigachat/judge.py", "name": "classify", "loc": 60, "call_count": 4},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)
    ranked_sources = [row["capability"] for row in ranked]

    assert set(ranked_sources[:3]) == {
        "app/providers/adapters.py:generate_result",
        "app/core/config.py:load_config",
        "app/gigachat/judge.py:classify",
    }
    assert ranked_sources[-1] == "app/api/server.py:lifespan"


def test_extraction_ranking_demotes_background_worker_wrapper():
    candidates = {}
    for item in [
        {"path": "downloader.py", "name": "worker", "loc": 140, "call_count": 24},
        {"path": "downloader.py", "name": "create_mbtiles", "loc": 90, "call_count": 5},
        {"path": "geocode_addresses.py", "name": "geocode", "loc": 80, "call_count": 5},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)

    assert ranked[0]["capability"] != "downloader.py:worker"


def test_extraction_ranking_prefers_descriptors_resource_probes_and_typed_llm_payloads():
    candidates = {}
    for item in [
        {"path": "p00420/api.py", "name": "build_plugin", "loc": 120, "call_count": 20},
        {"path": "p004/api.py", "name": "run_build_pipeline", "loc": 120, "call_count": 20},
        {"path": "p0041/_llm_client.py", "name": "extract_json_object", "loc": 80, "call_count": 12},
        {"path": "p0041/_llm_client.py", "name": "extract_llm_payload", "loc": 80, "call_count": 12},
        {"path": "p0041/api.py", "name": "describe_module", "loc": 30, "call_count": 2},
        {"path": "app/api/server.py", "name": "free_port", "loc": 25, "call_count": 2},
        {"path": "app/api/handlers_arena.py", "name": "call_provider_arena", "loc": 90, "call_count": 10},
    ]:
        add_extraction_candidate(candidates, item, "core_flow", "central flow")

    ranked = sorted(candidates.values(), key=extraction_candidate_sort_key)
    ranked_sources = [row["capability"] for row in ranked]

    assert "p0041/api.py:describe_module" in ranked_sources[:4]
    assert "app/api/server.py:free_port" in ranked_sources[:4]
    assert ranked_sources.index("p0041/_llm_client.py:extract_llm_payload") < ranked_sources.index(
        "p0041/_llm_client.py:extract_json_object"
    )
    assert ranked_sources.index("p00420/api.py:build_plugin") > ranked_sources.index("p0041/api.py:describe_module")
    assert ranked_sources.index("app/api/handlers_arena.py:call_provider_arena") > ranked_sources.index("app/api/server.py:free_port")

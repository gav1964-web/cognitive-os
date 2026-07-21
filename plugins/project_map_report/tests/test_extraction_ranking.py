from __future__ import annotations

from plugins.project_map_report.src.extraction_ranking import add_extraction_candidate, extraction_candidate_sort_key


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

from __future__ import annotations

from runtime.semantic_target_profiles import (
    contract_for_target,
    matching_profiles,
    semantic_ranking_adjustments,
    semantic_score_adjustments,
)


def test_semantic_target_profiles_match_scientific_contract_from_config():
    target = "numpy/lib/_function_base_impl.py:_quantile"

    profiles = matching_profiles(target)
    contract = contract_for_target(target)
    adjustments = semantic_score_adjustments(target)

    assert [profile["id"] for profile in profiles] == ["numeric_array_statistical_transform"]
    assert contract["contract_family"] == "numeric_array_statistical_transform"
    assert contract["input_contract"]["array_like_input"].startswith("ArrayLike")
    assert adjustments["score_delta"] == 20


def test_semantic_target_profiles_distinguish_framework_response_from_app_facade():
    framework = "src/flask/app.py:make_response"
    facade = "app.py:make_response"

    assert contract_for_target(framework)["contract_family"] == "web_framework_response_factory"
    assert contract_for_target(facade) == {}
    assert semantic_score_adjustments(framework)["score_delta"] == 20
    assert semantic_score_adjustments(facade)["score_delta"] == -18


def test_semantic_target_profiles_unknown_target_has_no_contract():
    target = "pkg/service.py:do_work"

    assert matching_profiles(target) == []
    assert contract_for_target(target) == {}
    assert semantic_score_adjustments(target)["score_delta"] == 0


def test_semantic_target_profiles_accept_scheduler_task_configuration_boundary():
    target = "src/pkg/_schedulers/async_.py:configure_task"

    contract = contract_for_target(target)

    assert contract["contract_family"] == "scheduled_task_configuration_boundary"
    assert semantic_score_adjustments(target)["score_delta"] == 20
    assert semantic_ranking_adjustments(target)["score_delta"] == 38


def test_semantic_target_profiles_accept_async_context_detection_boundary():
    target = "pkg/runtime/_impl.py:current_async_library"

    contract = contract_for_target(target)

    assert contract["contract_family"] == "async_context_detection_boundary"
    assert semantic_score_adjustments(target)["score_delta"] == 20
    assert semantic_ranking_adjustments(target)["score_delta"] == 38


def test_semantic_target_profiles_own_previous_domain_contract_fallbacks():
    cases = {
        "x31.py:generate_response": "ml_generation_boundary",
        "core/consensus/engine.py:run_consensus": "agent_consensus_orchestration_boundary",
        "AutoFix/auto_dev_agent.py:send_to_model": "llm_repair_hypothesis_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]


def test_semantic_target_profiles_cover_foundation_holdout_contract_families():
    cases = {
        "dask/array/blockwise.py:blockwise": "compute_graph_blockwise_construction_boundary",
        "lib/modulegraph/modulegraph.py:_find_head_package": "module_import_graph_resolution_boundary",
        "scrapy/crawler.py:_apply_settings": "crawler_settings_application_boundary",
        "src/airflow/api/common/trigger_dag.py:_trigger_dag": "workflow_dag_trigger_boundary",
        "transformers/processing_utils.py:apply_chat_template": "chat_template_rendering_boundary",
        "rest_framework/templatetags/rest_framework.py:add_query_param": "url_query_parameter_mutation_boundary",
        "bokeh/command/subcommands/serve.py:invoke": "command_entrypoint_invocation_boundary",
        "src/blib2to3/pgen2/driver.py:parse_file": "source_file_parser_boundary",
        "fastapi/dependencies/utils.py:analyze_param": "framework_dependency_parameter_analysis_boundary",
        "paramiko/client.py:connect": "ssh_client_connection_boundary",
        "main.py:cookiecutter": "template_project_generation_boundary",
        "locust/runners.py:handle_message": "runtime_message_dispatch_boundary",
        "mkdocs/commands/build.py:build": "static_site_build_boundary",
        "mypy/main.py:process_options": "cli_options_processing_boundary",
        "rest_framework/renderers.py:get_raw_data_form": "web_raw_data_form_rendering_boundary",
        "templates/project/{{ cookiecutter.repo_name }}/src/{{ cookiecutter.python_package }}/pipeline_registry.py:register_pipelines": "pipeline_registry_composition_boundary",
        "src/build/env.py:create": "isolated_build_environment_lifecycle_boundary",
        "uvicorn/protocols/websockets/websockets_sansio_impl.py:send": "websocket_protocol_send_boundary",
        "aiohttp/client.py:_ws_connect": "websocket_connection_setup_boundary",
        "src/anyio/_core/_sockets.py:connect_tcp": "connection_lifecycle_boundary",
        "httpie/core.py:program": "cli_program_pipeline_boundary",
        "pydantic/_internal/_model_construction.py:__new__": "model_construction_schema_boundary",
        "src/tox/session/cmd/run/common.py:_do_queue_and_wait": "test_environment_queue_execution_boundary",
        "isort/parse.py:file_contents": "code_quality_option_plugin_boundary",
        "src/pluggy/_callers.py:run_old_style_hookwrapper": "plugin_hook_invocation_boundary",
        "src/pluggy/_callers.py:_multicall": "plugin_hook_invocation_boundary",
        "poetry/console/commands/init.py:_init_pyproject": "package_project_initialization_boundary",
        "src/dateutil/parser/_parser.py:_parse": "datetime_string_parser_boundary",
        "boto3/resources/factory.py:load_from_definition": "sdk_resource_definition_factory_boundary",
        "backends/_quart.py:serve_websocket_callback": "websocket_callback_backend_boundary",
        "src/datasets/load.py:dataset_module_factory": "dataset_module_factory_boundary",
        "core/management/templates.py:handle": "framework_template_generation_boundary",
        "blocks.py:launch": "ml_app_launch_boundary",
        "contrib/capitalone_dataprofiler_expectations/capitalone_dataprofiler_expectations/expectations/expect_profile_numeric_columns_percent_diff_between_exclusive_threshold_range.py:_pandas": "data_expectation_metric_boundary",
        "prefect/flows.py:submit_to_work_pool": "workflow_work_pool_submission_boundary",
        "lib/sqlalchemy/dialects/oracle/base.py:translate_select_structure": "sql_select_translation_boundary",
        "transformers/tokenization_utils_tokenizers.py:convert_to_native_format": "tokenizer_native_conversion_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]


def test_semantic_target_profiles_cover_github20_foundation_gap_contracts():
    cases = {
        "certifi/core.py:contents": "package_resource_accessor_boundary",
        "src/werkzeug/debug/console.py:displayhook": "debug_console_display_boundary",
        "h11/_connection.py:our_state": "protocol_state_property_boundary",
        "httpx/_urlparse.py:urlparse": "url_parse_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        assert contract["contract_family"] == family
        assert isinstance(contract["input_contract"], dict)
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]


def test_profiled_contract_family_neutralizes_generic_trivial_penalty():
    from runtime.target_quality import semantic_target_quality_report

    for target in [
        "rest_framework/renderers.py:get_raw_data_form",
        "src/flake8/options/parse_args.py:parse_args",
    ]:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="ranking reason marks deterministic transform",
        )

        assert report["status"] == "strong"
        assert report["score"] >= 85


def test_semantic_target_profiles_demote_internal_rich_traverse_helper():
    public_target = "rich/pretty.py:traverse"
    internal_target = "rich/pretty.py:_traverse"

    assert matching_profiles(public_target)[0]["id"] == "terminal_render_traversal_boundary"
    assert contract_for_target(internal_target) == {}
    assert semantic_ranking_adjustments(public_target)["score_delta"] > 0
    assert semantic_ranking_adjustments(internal_target)["score_delta"] < 0

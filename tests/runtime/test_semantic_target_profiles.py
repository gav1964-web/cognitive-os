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
    assert adjustments["score_delta"] == 24


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
    assert semantic_score_adjustments(target)["score_delta"] == 22
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


def test_semantic_target_profiles_cover_unseen_spec_writer_contract_gaps():
    cases = {
        "frozenlist/__init__.py:__init__": "mutable_container_initialization_boundary",
        "multidict/_multidict_py.py:__setitem__": "mutable_mapping_assignment_boundary",
        "contrib/scrape-ec2-sizes.py:parse": "scraped_table_parser_boundary",
        "lib/yaml/parser.py:parse_flow_mapping_empty_value": "parser_state_transition_boundary",
        "gunicorn/workers/base.py:init_process": "process_worker_lifecycle_boundary",
        "falcon/asgi/app.py:__call__": "asgi_application_call_boundary",
        "src/quart/blueprints.py:register": "web_route_registration_boundary",
        "sanic/app.py:url_for": "web_url_generation_boundary",
        "packages/cfnresponse/cfnresponse.py:send": "cloudformation_response_send_boundary",
        "litestar/cli/_utils.py:_generate_self_signed_cert": "self_signed_certificate_generation_boundary",
        "src/hpack/hpack.py:_decode_literal": "hpack_literal_decode_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_semantic_target_profiles_cover_native_frontend_ml_stress_gaps():
    cases = {
        "setuptools_ext.py:add_rust_extension": "native_extension_bootstrap_boundary",
        "__init__.py:_get_sys_executable": "native_extension_bootstrap_boundary",
        "python/feast/api/registry/rest/data_sources.py:get_data_source_router": "web_router_factory_boundary",
        "assistant/providers/claude_code.py:astream": "async_provider_stream_boundary",
        "psycopg/psycopg/connection.py:connect": "database_connection_open_boundary",
        "src/airflow/policies.py:make_plugin_from_local_settings": "plugin_settings_registration_boundary",
        "src/lxml/html/soupparser.py:_init_node_converters": "converter_registry_initialization_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert adjustments["profiled_contract_family"] is True


def test_semantic_target_profiles_cover_blind_redteam_domain_gaps():
    cases = {
        "ansible/_internal/_ansiballz/_wrapper.py:_ansiballz_main": "self_extracting_runtime_wrapper_boundary",
        "conan/api/subapi/workspace.py:_parse_module": "workspace_module_parser_boundary",
        "src/cryptography/hazmat/asn1/asn1.py:_normalize_field_type": "asn1_schema_field_normalization_boundary",
        "pyvista/core/utilities/fileio.py:_read_grdecl": "scientific_mesh_file_reader_boundary",
        "rpm/build.py:srcfilter": "packaging_source_filter_boundary",
        "sympy/core/mul.py:_eval_subs": "symbolic_algebra_substitution_boundary",
        "domains/cpp/__init__.py:_resolve_xref_inner": "documentation_xref_resolution_boundary",
        "upgrade_extension.py:update_extension": "extension_upgrade_workflow_boundary",
        "celery/app/trace.py:build_tracer": "task_trace_builder_boundary",
        "src/click/core.py:_parse_decls": "cli_declaration_parser_boundary",
        "src/requests/sessions.py:resolve_redirects": "http_redirect_resolution_boundary",
        "src/_pytest/_py/path.py:make_numbered_dir": "numbered_temp_dir_allocation_boundary",
        "src/marshmallow/schema.py:_deserialize": "schema_deserialization_boundary",
        "typer/rich_utils.py:rich_format_help": "terminal_help_formatting_boundary",
        "dev/clint/src/clint/linter.py:lint_file": "lint_file_analysis_boundary",
        "src/werkzeug/serving.py:run_wsgi": "wsgi_serving_lifecycle_boundary",
        "bootstrap.py:_async_resolve_domains_and_preload": "domain_preload_bootstrap_boundary",
        "yarl/_url.py:build": "url_builder_normalization_boundary",
        "channels/auth.py:login": "session_auth_login_boundary",
        "uvloop/__init__.py:__getattr__": "native_module_api_facade_boundary",
        "numba/core/analysis.py:dead_branch_prune": "compiler_cfg_pruning_boundary",
        "bandit/formatters/custom.py:report": "security_scan_report_formatting_boundary",
        "tornado/template.py:_parse": "template_parser_boundary",
        "_src/jaxpr_util.py:jaxpr_to_html": "jaxpr_html_export_boundary",
        "zstandard/backend_cffi.py:train_dictionary": "compression_dictionary_training_boundary",
        "rustworkx/visualization/matplotlib.py:draw_edge_labels": "graph_edge_label_rendering_boundary",
        "client/commands/analyze.py:create_analyze_arguments": "cli_analysis_argument_schema_boundary",
        "pyright-internal/src/typeServer/protocol/generate_json.py:_parse_enums": "typescript_protocol_enum_parser_boundary",
        "src/msgspec/_utils.py:get_class_annotations": "python_type_annotation_extraction_boundary",
        "src/apscheduler/datastores/mongodb.py:acquire_jobs": "scheduled_job_acquisition_boundary",
        "limits/aio/storage/memcached/emcache.py:incr": "rate_limit_counter_increment_boundary",
        "arrow/arrow.py:dehumanize": "humanized_datetime_parse_boundary",
        "bottle.py:add": "web_route_mount_registration_boundary",
        "authlib/jose/rfc7516/jwe.py:serialize_json": "jose_json_serialization_boundary",
        "boltons/debugutils.py:wrap_trace": "debug_trace_wrapper_boundary",
        "src/webargs/pyramidparser.py:use_args": "request_args_binding_boundary",
        "src/engineio/async_client.py:_connect_websocket": "engineio_websocket_connection_boundary",
        "src/socketio/async_client.py:connect": "engineio_websocket_connection_boundary",
        "src/flask_principal.py:init_app": "flask_extension_initialization_boundary",
        "pyramid/config/routes.py:add_route": "web_route_registration_boundary",
        "graphene/types/schema.py:create_fields_for_type": "graphql_type_field_factory_boundary",
        "jwt/api_jwt.py:_validate_claims": "jwt_claim_validation_boundary",
        "src/cattrs/gen/typeddicts.py:make_dict_structure_fn": "typed_dict_structure_function_factory_boundary",
        "annotation.py:_resolve_evaled_type": "graphql_annotation_resolution_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_semantic_target_profiles_cover_blind_redteam_20f_gaps():
    cases = {
        "__init__.py:AsyncHttpClient": "async_http_client_facade_boundary",
        "fsspec/implementations/http.py:_ls_real": "http_filesystem_listing_boundary",
        "services/kernels/connection/channels.py:nudge": "kernel_channel_nudge_boundary",
        "core/langchain_core/_api/deprecation.py:deprecated": "deprecation_decorator_boundary",
        "openai/_legacy_response.py:_parse": "legacy_response_parse_boundary",
        "optuna/samplers/_cmaes.py:sample_relative": "optimizer_relative_sampler_boundary",
        "src/_skimage2/feature/_daisy.py:daisy": "image_feature_descriptor_boundary",
        "qdrant_client/local/local_collection.py:search": "vector_collection_search_boundary",
        "src/installer/utils.py:parse_entrypoints": "python_entrypoint_parse_boundary",
        "poetry/core/packages/dependency.py:create_from_pep_508": "pep508_dependency_parse_boundary",
        "localstack/config.py:parse": "environment_config_parse_boundary",
        "_mmio.py:_write": "scientific_matrix_market_write_boundary",
        "automation/automation/dagster_docs/docstring_rules/section_header_rule.py:validate_section_headers": "docstring_section_validation_boundary",
        "src/structlog/_native.py:_make_filtering_bound_logger": "logging_filtering_bound_logger_factory_boundary",
        "contrib/capitalone_dataprofiler_expectations/capitalone_dataprofiler_expectations/rule_based_profiler/domain_builder/data_profiler_column_domain_builder.py:_get_domains": "data_profiler_column_domain_builder_boundary",
        "src/webob/compat.py:read_multi": "multipart_form_read_boundary",
        "src/textual/_xterm_parser.py:parse": "xterm_terminal_sequence_parser_boundary",
        "rich/pretty.py:traverse": "terminal_render_traversal_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_semantic_target_profiles_cover_blind_redteam_40c_gaps():
    cases = {
        "src/blinker/base.py:connect": "signal_subscription_boundary",
        "src/cachelib/dynamodb.py:_set": "cache_operation_boundary",
        "src/flask_caching/__init__.py:memoize": "cache_operation_boundary",
        "dogpile/cache/region.py:cache_multi_on_arguments": "cache_operation_boundary",
        "jsonschema_specifications/_core.py:_schemas": "schema_resource_registry_boundary",
        "src/twisted/application/_client_service.py:makeMachine": "state_machine_factory_boundary",
        "src/pytest_benchmark/fixture.py:_raw": "benchmark_fixture_measurement_boundary",
        "src/OpenSSL/crypto.py:__setattr__": "crypto_attribute_bridge_boundary",
        "src/protego/_protego.py:_extract_directive": "robots_directive_parser_boundary",
        "mako/codegen.py:write_namespaces": "template_codegen_namespace_boundary",
        "itemloaders/__init__.py:_get_jmesvalues": "item_value_extraction_boundary",
        "itemadapter/_json_schema.py:_json_schema_from_dataclass": "python_type_annotation_extraction_boundary",
        "src/pytest_rerunfailures.py:evaluate_condition": "plugin_condition_evaluation_boundary",
        "pytest_timeout.py:pytest_timeout_set_timer": "plugin_condition_evaluation_boundary",
        "src/pytest_html/basereport.py:pytest_runtest_logreport": "plugin_condition_evaluation_boundary",
        "queuelib/queue.py:push": "queue_push_boundary",
        "async_generator/_impl.py:yield_from_": "async_generator_delegation_boundary",
        "src/chardet/__init__.py:detect_all": "encoding_detection_boundary",
        "glom/core.py:register_op": "object_path_operation_registry_boundary",
        "src/zope/interface/verify.py:_verify_element": "interface_verification_boundary",
        "autoflake.py:multiline_statement": "source_statement_boundary_detection",
        "src/zope/event/classhandler.py:dispatch": "event_dispatch_routing_boundary",
        "pytest_django/plugin.py:_fail_for_invalid_template_variable": "template_variable_validation_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


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


def test_semantic_target_profiles_cover_blind_redteam_40k_gaps():
    cases = {
        "src/awkward/_slicing.py:_normalise_item_bool_to_int": "array_slice_normalization_boundary",
        "src/cffi/backend_ctypes.py:complete_struct_or_union": "ffi_struct_completion_boundary",
        "src/hist/plot.py:plot_ratio_array": "plot_ratio_array_boundary",
        "src/nacl/bindings/crypto_secretstream.py:crypto_secretstream_xchacha20poly1305_pull": "crypto_secretstream_pull_boundary",
        "src/OpenSSL/crypto.py:__setattr__": "crypto_attribute_bridge_boundary",
        "src/protego/_protego.py:_extract_directive": "robots_directive_parser_boundary",
        "src/uproot/behaviors/RNTuple.py:arrays": "scientific_tree_array_read_boundary",
        "src/vector/_compute/lorentz/add.py:dispatch": "vector_compute_dispatch_boundary",
        "numpy/lib/_function_base_impl.py:_quantile": "numeric_array_statistical_transform",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_blind_redteam_40l_gaps():
    cases = {
        "Lib/fontTools/designspaceLib/split.py:_extractSubSpace": "font_designspace_subspace_extraction_boundary",
        "src/PIL/Image.py:convert": "image_mode_conversion_transform",
        "shapely/_ragged_array.py:_get_arrays_multilinestring": "geometry_ragged_array_extraction_boundary",
        "vine/promises.py:throw": "promise_error_propagation_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24

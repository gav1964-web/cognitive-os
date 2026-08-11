from __future__ import annotations

from runtime.contract_archetype_inference import (
    archetype_score_adjustments,
    contract_archetype_for_target,
    matching_archetypes,
)
from runtime.target_quality import semantic_target_quality_report


def test_contract_archetype_inference_matches_generalized_holdout_shapes():
    cases = {
        "src/attr/_make.py:_create_slots_class": "class_synthesis_factory",
        "src/urllib3/connectionpool.py:urlopen": "protocol_request_transaction",
        "more_itertools/more.py:distinct_permutations": "combinatorial_iterator_generation",
        "src/itsdangerous/url_safe.py:load_payload": "payload_serializer_loader",
        "src/jinja2/compiler.py:visit_For": "compiler_ast_visitor",
        "src/iniconfig/_parse.py:_parseline": "configuration_line_parser",
        "alive_progress/core/configuration.py:create_config": "configuration_object_factory",
        "twine/auth.py:_make_trusted_publishing_token": "trusted_token_acquisition",
        "h11/_connection.py:_process_event": "protocol_state_event_processor",
        "src/outcome/_impl.py:acapture": "async_result_capture",
        "src/pyprojectx/requirements.py:_get_or_add_requirements": "dependency_requirement_set_update",
        "serial/serialwin32.py:read": "serial_stream_read",
        "src/sortedcontainers/sortedlist.py:__getitem__": "ordered_collection_index_lookup",
        "referencing/_core.py:lookup": "resource_reference_lookup",
        "src/argon2/_utils.py:extract_parameters": "password_hash_parameter_extraction",
        "pool.py:_join_exited_workers": "worker_pool_lifecycle_join",
        "zipp/glob.py:translate_core": "glob_pattern_translation",
        "jsonschema/validators.py:create": "validator_factory",
        "starlette/authentication.py:requires": "permission_gate_decorator",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert matching_archetypes(target)[0]["id"] == archetype
        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_target_quality_uses_contract_archetype_as_generalized_family():
    report = semantic_target_quality_report(
        "transport/http_client.py:urlopen",
        ranked_candidates=["transport/http_client.py:urlopen"],
        source_evidence=["transport/http_client.py:urlopen"],
    )

    assert report["status"] == "strong"
    assert report["score"] >= 95
    assert report["profiled_contract_family"] is True
    assert report["contract_archetype_ids"] == ["protocol_request_transaction"]


def test_exact_semantic_profile_takes_precedence_over_matching_archetype():
    target = "src/urllib3/connectionpool.py:urlopen"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["profiled_contract_family"] is True
    assert report["semantic_profile_ids"]
    assert report["contract_archetype_ids"] == []


def test_contract_archetype_inference_covers_generalized_40c_shapes():
    cases = {
        "eventbus/subscription.py:connect": "event_subscription_registration",
        "services/cache_backend.py:memoize": "cache_key_value_operation",
        "lifecycle/state_machine.py:make_machine": "state_machine_construction",
        "lint/source_parser.py:multiline_statement": "source_statement_boundary_parser",
        "events/dispatcher.py:dispatch": "event_dispatch_routing",
        "render/template_checks.py:fail_for_invalid_template_variable": "template_variable_failure_policy",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contract_archetype_inference_covers_generalized_40d_shapes():
    cases = {
        "src/hyperlink/_url.py:from_text": "url_text_parsing",
        "aiodns/compat.py:_convert_record": "dns_record_conversion",
        "src/pytest_subtests/plugin.py:__exit__": "pytest_plugin_lifecycle_hook",
        "pytest_repeat.py:__pytest_repeat_step_number": "pytest_plugin_lifecycle_hook",
        "src/pytest_randomly/__init__.py:pytest_configure": "pytest_plugin_lifecycle_hook",
        "src/oic/oauth2/provider.py:auth_init": "oauth_authorization_initialization",
        "redis/maint_notifications.py:handle_oss_maintenance_completed_notification": "command_notification_handler",
        "model_utils/tracker.py:finalize_class": "class_instrumentation_finalization",
        "checkers/typecheck.py:visit_call": "lint_ast_call_visitor",
        "mccabe.py:visitFunctionDef": "lint_ast_call_visitor",
        "src/flask_mail/__init__.py:sanitize_address": "email_address_normalization",
        "eradicate.py:comment_contains_code": "source_comment_code_detection",
        "aioredis/client.py:acl_setuser": "redis_acl_command_builder",
        "src/zope/component/zcml.py:adapter": "component_adapter_registration",
        "src/prompt_toolkit/application/application.py:run_async": "interactive_application_run_loop",
        "src/service_identity/hazmat.py:from_bytes": "encoded_identity_value_loader",
        "src/zope/testing/formparser.py:parse": "html_form_parser",
        "src/zope/testing/doctestcase.py:_run_test": "doctest_case_execution",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contract_archetype_inference_covers_generalized_40e_shapes():
    cases = {
        "aiohttp_session/nacl_storage.py:load_session": "encrypted_session_storage_load",
        "aiomysql/connection.py:caching_sha2_password_auth": "database_auth_handshake",
        "aiosmtpd/smtp.py:smtp_DATA": "protocol_command_handler",
        "src/apispec/core.py:_clean_operations": "api_schema_operation_normalization",
        "reporter/junit.py:_process_scenario": "test_report_rendering",
        "src/doc8/parser.py:document": "documentation_source_parser",
        "django_celery_beat/schedulers.py:_get_crontab_exclude_query": "django_query_or_admin_action",
        "django_celery_results/admin.py:terminate_task": "django_query_or_admin_action",
        "configurations/utils.py:getargspec": "introspection_signature_adapter",
        "constance/admin.py:history_view": "django_query_or_admin_action",
        "django_filters/utils.py:__new__": "django_query_or_admin_action",
        "django_redis/client/default.py:incr_version": "django_query_or_admin_action",
        "taggit/managers.py:similar_objects": "django_query_or_admin_action",
        "cli.py:execute": "provider_cli_execution",
        "httpretty/core.py:parse_querystring": "http_multipart_request_matcher",
        "responses/matchers.py:multipart_matcher": "http_multipart_request_matcher",
        "src/wrapt/synchronization.py:synchronized": "synchronization_decorator_boundary",
        "bugbear.py:check_for_b041": "lint_rule_checker",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contract_archetype_inference_covers_generalized_40f_shapes():
    cases = {
        "src/aiofiles/tempfile/__init__.py:_temporary_file": "async_resource_context_boundary",
        "async_timeout/__init__.py:timeout": "async_resource_context_boundary",
        "src/lazy_object_proxy/utils.py:await_": "async_resource_context_boundary",
        "compressor/contrib/sekizai.py:compress": "template_render_or_compression_boundary",
        "crispy_forms/templatetags/crispy_forms_field.py:render": "template_render_or_compression_boundary",
        "django_extensions/management/shells.py:import_objects": "django_framework_operation_boundary",
        "guardian/admin.py:obj_perms_manage_view": "django_framework_operation_boundary",
        "modeltranslation/translator.py:add_translation_fields": "django_framework_operation_boundary",
        "src/polymorphic/query.py:_get_real_instances": "django_framework_operation_boundary",
        "simple_history/utils.py:bulk_create_with_history": "django_framework_operation_boundary",
        "waffle/management/commands/waffle_flag.py:handle": "django_framework_operation_boundary",
        "src/pytest_bdd/scenario.py:_get_scenario_decorator": "pytest_fixture_or_decorator_registration",
        "src/pytest_factoryboy/fixturegen.py:inner": "pytest_fixture_or_decorator_registration",
        "flake8_docstrings.py:_call_check_source": "source_checker_predicate",
        "src/flake8_comprehensions/__init__.py:has_double_star_args": "source_checker_predicate",
        "src/pytestqt/modeltest.py:_check_children": "source_checker_predicate",
        "src/sqlacodegen/generators.py:fix_column_types": "schema_type_normalization_boundary",
        "aiohttp_remotes/basic_auth.py:middleware": "web_auth_middleware_boundary",
        "src/flask_login/login_manager.py:needs_refresh": "web_auth_middleware_boundary",
        "src/flask_migrate/templates/flask-multidb/env.py:run_migrations_online": "migration_runtime_execution_boundary",
        "playhouse/migrations.py:template": "migration_runtime_execution_boundary",
        "haystack/backends/whoosh_backend.py:search": "search_backend_query_boundary",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contract_archetype_inference_covers_generalized_40g_shapes():
    cases = {
        "src/apispec_webframeworks/tornado.py:tornadopath2openapi": "openapi_route_path_conversion",
        "src/croniter/croniter.py:croniter_range": "schedule_range_generation",
        "databases/backends/aiopg.py:_compile": "database_query_compile_boundary",
        "base.py:set": "configuration_state_assignment_boundary",
        "inflection/__init__.py:camelize": "string_case_slug_transform",
        "slugify/slugify.py:slugify": "string_case_slug_transform",
        "jaraco/text/__init__.py:join_continuation": "string_case_slug_transform",
        "jaraco/classes/properties.py:__setattr__": "descriptor_property_assignment_boundary",
        "jaraco/context/__init__.py:raises": "exception_context_assertion_boundary",
        "bin/sort.py:_test_sort": "classifier_catalog_sort_boundary",
        "src/typing_extensions.py:__new__": "typing_construct_factory",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contract_archetype_inference_covers_generalized_40h_shapes():
    cases = {
        "benchmarking/format_results.py:load_benchmarking_results": "benchmark_result_loader",
        "colorama/winterm.py:erase_screen": "terminal_color_control_boundary",
        "coloredlogs/tests.py:test_plain_text_output_format": "logging_output_format_boundary",
        "src/pythonjsonlogger/core.py:format": "logging_output_format_boundary",
        "docutils/parsers/rst/states.py:substitution_def": "documentation_markup_parser_boundary",
        "frontmatter/__init__.py:parse": "documentation_markup_parser_boundary",
        "xmltodict.py:parse": "documentation_markup_parser_boundary",
        "jmespath/parser.py:_token_nud_lbracket": "query_expression_parser_boundary",
        "jsonpath_ng/_ply/yacc.py:parsedebug": "query_expression_parser_boundary",
        "src/humanize/time.py:naturaldelta": "localized_value_format_boundary",
        "python/phonenumbers/phonenumberutil.py:format_out_of_country_keeping_alpha_chars": "localized_value_format_boundary",
        "decouple.py:_find_file": "configuration_file_discovery_boundary",
        "magic/__init__.py:_add_compat": "configuration_file_discovery_boundary",
        "schedule/__init__.py:at": "scheduler_job_definition_boundary",
        "src/watchdog/watchmedo.py:auto_restart": "scheduler_job_definition_boundary",
        "sqlmodel/_compat.py:sqlmodel_table_construct": "orm_model_table_or_relation_boundary",
        "tortoise/backends/base/executor.py:_prefetch_m2m_relation": "orm_model_table_or_relation_boundary",
        "shortuuid/main.py:set_alphabet": "identifier_alphabet_configuration_boundary",
        "ninja/signature/details.py:_get_param_type": "web_framework_signature_param_inference",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True


def test_contextual_archetype_inference_covers_public_formatter_facade():
    report = semantic_target_quality_report(
        "__init__.py:format",
        ranked_candidates=["__init__.py:format"],
        source_evidence=["__init__.py:format"],
        context_evidence=["pygments"],
    )

    assert report["status"] == "strong"
    assert report["contract_archetype_ids"] == ["syntax_highlight_format_boundary"]
    assert report["score"] >= 97


def test_contract_archetype_inference_covers_generalized_40i_shapes():
    cases = {
        "dacite/core.py:_build_value": "data_object_construction_boundary",
        "core/meta/code/builder.py:_add_unpack_method_lines": "data_object_construction_boundary",
        "deepdiff/deephash.py:_hash": "diff_hash_patch_boundary",
        "dictdiffer/__init__.py:patch": "diff_hash_patch_boundary",
        "distributed/worker.py:close": "distributed_resource_lifecycle_boundary",
        "joblib/_memmapping_reducer.py:__call__": "distributed_resource_lifecycle_boundary",
        "frictionless/analyzer/analyzer.py:_statistics": "formula_statistics_transform_boundary",
        "formulaic/transforms/contrasts.py:encode_contrasts": "formula_statistics_transform_boundary",
        "patsy/mgcv_cubic_splines.py:test_crs_with_specific_constraint": "formula_statistics_transform_boundary",
        "imageio/core/imopen.py:imopen": "document_image_io_boundary",
        "pypdf/_writer.py:merge": "document_image_io_boundary",
        "barcode/writer.py:render": "document_image_io_boundary",
        "src/docx/comments.py:add_comment": "document_image_io_boundary",
        "src/pptx/oxml/table.py:new_tbl": "document_image_io_boundary",
        "xlsxwriter/chart.py:_write_date_axis": "document_image_io_boundary",
        "num2words/lang_TR.py:to_cardinal": "localized_number_word_format_boundary",
        "nltk/app/chunkparser_app.py:_init_widgets": "interactive_widget_initialization_boundary",
        "altair/utils/core.py:parse_shorthand": "visual_encoding_shorthand_parse_boundary",
        "archive/descstats.py:descstats": "descriptive_statistics_summary_boundary",
    }

    for target, archetype in cases.items():
        contract = contract_archetype_for_target(target)
        adjustments = archetype_score_adjustments(target)

        assert contract["contract_archetype"] == archetype
        assert contract["contract_family"] == archetype
        assert adjustments["profiled_contract_family"] is True


def test_target_quality_scores_remaining_40i_profiled_edges_as_strong():
    cases = [
        "networkx/algorithms/graph_hashing.py:weisfeiler_lehman_subgraph_hashes",
        "nltk/app/chunkparser_app.py:_init_widgets",
        "altair/utils/core.py:parse_shorthand",
        "archive/descstats.py:descstats",
        "seaborn/categorical.py:catplot",
    ]

    for target in cases:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
        )

        assert report["status"] == "strong"
        assert report["score"] >= 97


def test_target_quality_keeps_parser_helper_profile_acceptable_until_executable_proof():
    target = "pyparsing/helpers.py:one_of"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["status"] == "acceptable"
    assert report["score"] == 84


def test_target_quality_does_not_double_count_archetype_when_exact_profile_exists():
    target = "src/blinker/base.py:connect"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["score"] == 96
    assert report["semantic_profile_ids"] == ["signal_subscription_boundary"]
    assert report["contract_archetype_ids"] == []


def test_profiled_prompt_toolkit_target_is_not_meta_infrastructure():
    target = "src/prompt_toolkit/application/application.py:run_async"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
    )

    assert report["status"] == "strong"
    assert report["profiled_contract_family"] is True
    assert report["contract_archetype_ids"] == ["interactive_application_run_loop"]
    assert not any("meta-infrastructure" in reason for reason in report["reasons"])


def test_serial_read_archetype_does_not_match_read_substrings():
    false_matches = [
        "aiopg/connection.py:_ready",
        "aiosqlite/core.py:_connection_worker_thread",
    ]

    for target in false_matches:
        assert contract_archetype_for_target(target) == {}
        assert archetype_score_adjustments(target)["profiled_contract_family"] is False

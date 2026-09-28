from __future__ import annotations

from runtime.semantic_target_profiles import (
    contract_for_target,
    semantic_ranking_adjustments,
    semantic_score_adjustments,
)
from runtime.target_quality import semantic_target_quality_report


def test_semantic_target_profiles_cover_blind_redteam_40m_gaps():
    cases = {
        "src/aiohappyeyeballs/impl.py:start_connection": "connection_lifecycle_boundary",
        "__init__.py:__getattr__": "native_module_api_facade_boundary",
        "astroquery/alma/core.py:_parse_stcs_string": "stcs_region_parser_boundary",
        "__init__.py:add_alias_finder": "cli_alias_registration_boundary",
        "src/enrich/console.py:print": "console_print_adapter_boundary",
        "github/Branch.py:edit_protection": "github_branch_protection_update_boundary",
        "src/semantic_release/commit_parser/util.py:parse_paragraphs": "commit_message_paragraph_parser_boundary",
        "redis/maint_notifications.py:handle_oss_maintenance_completed_notification": "redis_maintenance_notification_boundary",
        "S3/FileLists.py:fetch_local_list": "s3_local_file_inventory_boundary",
        "s3transfer/download.py:_schedule_remaining_chunks": "s3_transfer_chunk_scheduler_boundary",
        "sqlparse/filters/reindent.py:_process_identifierlist": "sql_token_reindent_boundary",
        "sunpy/coordinates/ephemeris.py:get_horizons_coord": "solar_ephemeris_query_boundary",
        "tenacity/tornadoweb.py:__call__": "retry_wrapper_call_boundary",
        "tqdm/tk.py:__init__": "progress_widget_initialization_boundary",
        "typing_inspect.py:get_args": "typing_args_extraction_boundary",
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


def test_semantic_target_profiles_cover_blind_redteam_40n_gaps():
    cases = {
        "coverage/cmdline.py:command_line": "coverage_analysis_report_boundary",
        "src/dependency_injector/wiring.py:_bind_injections": "dependency_injection_wiring_boundary",
        "requests_mock/response.py:create_response": "http_mock_response_factory_boundary",
        "vcs-versioning/src/vcs_versioning/_worktree_discovery.py:discover_workdir": "vcs_worktree_version_discovery_boundary",
        "src/tox/session/cmd/run/common.py:execute": "test_environment_queue_execution_boundary",
        "src/wheel/_commands/info.py:info": "wheel_tag_artifact_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_weaktypes_40_gaps():
    cases = {
        "auditwheel/repair.py:repair_wheel": "native_wheel_repair_boundary",
        "lib/cartopy/io/ogc_clients.py:_wmts_images": "geospatial_tile_render_boundary",
        "entrypoints.py:iter_files_distros": "python_entrypoint_discovery_boundary",
        "fiona/fio/collect.py:collect": "geospatial_feature_io_boundary",
        "geopandas/plotting.py:plot_dataframe": "geodataframe_plot_mapping_boundary",
        "analytics/management_v3_reference.py:traverse_hierarchy": "generated_sdk_resource_traversal_boundary",
        "httpie/core.py:program": "cli_program_pipeline_boundary",
        "pandas/core/algorithms.py:isin": "tabular_array_construction_transform",
        "__main__.py:print_includes": "native_extension_compiler_flags_boundary",
        "__init__.py:sdist": "pep517_sdist_build_boundary",
        "rasterio/merge.py:merge": "raster_mosaic_transform_boundary",
        "sklearn/calibration.py:_sigmoid_calibration": "ml_metric_calibration_transform",
        "stevedore/driver.py:_init_plugins": "python_entrypoint_discovery_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_weaktypes_12_gaps():
    cases = {
        "msgpack/fallback.py:_pack": "binary_message_pack_codec_boundary",
        "src/netCDF4/utils.py:nc3tonc4": "netcdf_format_conversion_boundary",
        "cpp/src/arrow/acero/hash_join_graphs.py:plot_3d": "arrow_hash_join_graph_visualization_boundary",
        "shap/plots/_beeswarm.py:summary_legacy": "model_explainability_plot_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_foundation_holdout_b_gaps():
    cases = {
        "spacy/cli/find_threshold.py:find_threshold": "ml_threshold_search_boundary",
        "src/watchgha/watch_runs.py:watch": "ci_run_watch_event_boundary",
        "identify/identify.py:parse_shebang": "source_shebang_command_parser_boundary",
        "pyparsing/helpers.py:one_of": "parser_combinator_helper_boundary",
        "src/semantic_release/version/declarations/parser.py:parse_version": "release_version_parser_boundary",
        "src/semantic_release/version/algorithm.py:next_version": "release_version_planning_boundary",
        "src/semantic_release/cli/commands/version.py:version": "release_version_planning_boundary",
        "llama_index/core/agent/workflow/base_agent.py:parse_agent_output": "agent_workflow_output_parser_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_cover_foundation_holdout_c_gaps():
    cases = {
        "mirror.py:get_current_version": "precommit_mirror_version_discovery_boundary",
        "certifi/core.py:contents": "package_resource_accessor_boundary",
        "tlz/_build_tlz.py:exec_module": "module_exec_facade_boundary",
        "sphinx_rtd_theme/__init__.py:config_initiated": "sphinx_theme_config_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"] or family == "package_resource_accessor_boundary"
        assert contract["output_contract"]
        assert contract["validation_gates"]
        assert contract["failure_modes"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 22


def test_semantic_target_profiles_cover_python_owned_boundary_40_gaps():
    cases = {
        "cloudpickle/cloudpickle.py:_function_getstate": "python_function_state_serialization_boundary",
        "dill/session.py:load_module": "python_module_session_load_boundary",
        "src/execnet/rsync_remote.py:receive_directory_structure": "rsync_directory_manifest_receive_boundary",
        "__init__.py:add_shared_build_options": "build_backend_shared_options_boundary",
        "src/pydicom/pixels/decoders/gdcm.py:_decode_frame": "medical_pixel_frame_decode_boundary",
        "bson/json_util.py:_parse_canonical_datetime": "canonical_datetime_json_parse_boundary",
        "aiosignal/__init__.py:send": "async_signal_dispatch_boundary",
        "soupsieve/css_parser.py:parse_selectors": "css_selector_parse_boundary",
        "src/markupsafe/__init__.py:escape": "html_markup_escape_boundary",
        "src/trio/_core/_run.py:unrolled_run": "async_kernel_run_loop_boundary",
        "lmfit/minimizer.py:brute": "numerical_brute_force_optimization_boundary",
    }

    for target, family in cases.items():
        contract = contract_for_target(target)
        adjustments = semantic_score_adjustments(target)

        assert contract["contract_family"] == family
        assert contract["input_contract"]
        assert contract["output_contract"]
        assert adjustments["profiled_contract_family"] is True
        assert adjustments["score_delta"] >= 24


def test_semantic_target_profiles_ignore_callable_loc_annotations():
    contract = contract_for_target("aiosignal/__init__.py:send(9 loc)")
    adjustments = semantic_score_adjustments("aiosignal/__init__.py:send(9 loc)")

    assert contract["contract_family"] == "async_signal_dispatch_boundary"
    assert adjustments["profiled_contract_family"] is True


def test_semantic_target_profiles_cover_unified_pipeline_worst_cases():
    cases = {
        "aiopg/sa/connection.py:execute": (
            "async_sql_query_execution_boundary",
            38,
        ),
        "aiosqlite/core.py:_execute": (
            "async_worker_call_dispatch_boundary",
            38,
        ),
        "faust/assignor/copartitioned_assignor.py:_assign_round_robin": (
            "partition_assignment_planning_boundary",
            40,
        ),
        "src/tablib/formats/_latex.py:_colspec": (
            "tabular_column_specification_boundary",
            36,
        ),
    }

    for target, (family, minimum_ranking_bonus) in cases.items():
        contract = contract_for_target(target)
        ranking = semantic_ranking_adjustments(target)
        quality = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
        )

        assert contract["contract_family"] == family
        assert contract["validation_gates"]
        assert ranking["score_delta"] >= minimum_ranking_bonus
        assert quality["profiled_contract_family"] is True
        assert quality["score"] >= 97


def test_async_execute_profiles_do_not_match_generic_execute_symbol():
    target = "package/core.py:execute"

    assert contract_for_target(target) == {}
    assert semantic_ranking_adjustments(target)["score_delta"] == 0

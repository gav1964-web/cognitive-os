from __future__ import annotations

from runtime.target_quality import semantic_target_quality_report, target_quality_report


def test_target_quality_marks_representative_target_good():
    report = target_quality_report(
        {
            "selected_extraction_candidate": "src/prefect/task_engine.py:_create_task_run_locally",
            "implementation_binding_status": "bound_to_extraction_contract",
            "test_has_contract_matrix": True,
            "test_has_negative_tests_for_target": True,
        }
    )

    assert report["status"] == "good"
    assert "representative domain target" in " ".join(report["reasons"])


def test_target_quality_flags_utility_target_as_suspicious():
    report = target_quality_report(
        {
            "selected_extraction_candidate": "spyder/api/widgets/mixins.py:svg_to_scaled_pixmap",
            "implementation_binding_status": "bound_to_extraction_contract",
            "test_has_contract_matrix": True,
            "test_has_negative_tests_for_target": True,
        }
    )

    assert report["status"] == "suspicious"
    assert "suspicious utility/support target" in " ".join(report["reasons"])


def test_target_quality_marks_missing_target_blocked():
    report = target_quality_report({"selected_extraction_candidate": ""})

    assert report["status"] == "blocked"


def test_semantic_target_quality_accepts_bounded_factory_contract():
    report = semantic_target_quality_report(
        "app/providers/factory.py:build_providers_from_config",
        ranked_candidates=["app/providers/factory.py:build_providers_from_config"],
        source_evidence=["app/providers/factory.py:build_providers_from_config"],
        selection_reason="central flow node; input contract can be inferred from signature",
    )

    assert report["status"] == "strong"
    assert report["score"] >= 85


def test_semantic_target_quality_flags_meta_runtime_targets():
    meta = semantic_target_quality_report(
        "p0048/_capability_acquisition.py:acquire_capability",
        ranked_candidates=["p0048/_capability_acquisition.py:acquire_capability"],
        source_evidence=["p0048/_capability_acquisition.py:acquire_capability"],
    )
    boundary = semantic_target_quality_report(
        "app/main.py:provider_url",
        ranked_candidates=["app/main.py:provider_url"],
        source_evidence=["app/main.py:provider_url"],
    )

    assert meta["status"] in {"suspicious", "poor"}
    assert boundary["status"] in {"suspicious", "poor"}


def test_semantic_target_quality_accepts_llm_repair_hypothesis_boundary():
    report = semantic_target_quality_report(
        "AutoFix/auto_dev_agent.py:send_to_model",
        ranked_candidates=["AutoFix/auto_dev_agent.py:send_to_model"],
        source_evidence=["AutoFix/auto_dev_agent.py:send_to_model"],
        selection_reason="LLM hypothesis boundary is central to repair-attempt contract",
    )

    assert report["status"] == "strong"
    assert "LLM repair hypothesis boundary" in " ".join(report["reasons"])


def test_semantic_target_quality_does_not_treat_iniconfig_as_icon_utility():
    report = semantic_target_quality_report(
        "src/iniconfig/_parse.py:parse_ini_data",
        ranked_candidates=["src/iniconfig/_parse.py:parse_ini_data"],
        source_evidence=["src/iniconfig/_parse.py:parse_ini_data"],
        selection_reason="deterministic parser/normalizer/validator shape",
    )

    assert report["status"] == "strong"
    assert "icon" not in " ".join(report["reasons"])


def test_semantic_target_quality_penalizes_string_facade_over_markup_escape_boundary():
    weak = semantic_target_quality_report(
        "src/markupsafe/__init__.py:capitalize",
        ranked_candidates=["src/markupsafe/__init__.py:capitalize"],
        source_evidence=["src/markupsafe/__init__.py:capitalize"],
        selection_reason="pure transform candidate",
    )
    strong = semantic_target_quality_report(
        "src/markupsafe/__init__.py:escape",
        ranked_candidates=["src/markupsafe/__init__.py:escape"],
        source_evidence=["src/markupsafe/__init__.py:escape"],
        selection_reason="pure transform candidate",
    )

    assert weak["status"] in {"suspicious", "poor"}
    assert strong["status"] == "strong"


def test_semantic_target_quality_accepts_connection_lifecycle_boundary():
    report = semantic_target_quality_report(
        "httpcore/_async/socks_proxy.py:_init_socks5_connection",
        ranked_candidates=["httpcore/_async/socks_proxy.py:_init_socks5_connection"],
        source_evidence=["httpcore/_async/socks_proxy.py:_init_socks5_connection"],
        selection_reason="input contract can be inferred from signature",
    )

    assert report["status"] == "strong"


def test_semantic_target_quality_accepts_exception_formatting_boundary():
    report = semantic_target_quality_report(
        "py/_code/_py2traceback.py:format_exception_only",
        ranked_candidates=["py/_code/_py2traceback.py:format_exception_only"],
        source_evidence=["py/_code/_py2traceback.py:format_exception_only"],
        selection_reason="bounded data-shaping helper is a better extraction target",
    )

    assert report["score"] >= 95
    assert report["status"] == "strong"


def test_semantic_target_quality_accepts_signed_token_boundary():
    report = semantic_target_quality_report(
        "src/itsdangerous/timed.py:unsign",
        ranked_candidates=["src/itsdangerous/timed.py:unsign"],
        source_evidence=["src/itsdangerous/timed.py:unsign"],
    )

    assert report["score"] >= 95
    assert report["status"] == "strong"


def test_semantic_target_quality_penalizes_cli_bootstrap_helpers():
    parse_args = semantic_target_quality_report(
        "prompt_lab.py:parse_args",
        ranked_candidates=["prompt_lab.py:parse_args"],
        source_evidence=["prompt_lab.py:parse_args"],
        selection_reason="deterministic parser/normalizer/validator shape",
    )
    ignored = semantic_target_quality_report(
        "map.py:is_ignored",
        ranked_candidates=["map.py:is_ignored"],
        source_evidence=["map.py:is_ignored"],
        selection_reason="pure transform candidate",
    )

    assert parse_args["status"] in {"suspicious", "poor"}
    assert ignored["status"] in {"suspicious", "poor"}


def test_semantic_target_quality_allows_prompt_lab_first_slice_target():
    report = semantic_target_quality_report(
        "prompt_lab.py:analyze_validation_results",
        ranked_candidates=["prompt_lab.py:analyze_validation_results"],
        source_evidence=["prompt_lab.py:analyze_validation_results"],
        selection_reason="ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
    )

    assert report["status"] in {"acceptable", "strong"}
    assert report["score"] >= 65


def test_semantic_target_quality_accepts_calculate_provider_and_mock_contracts():
    calculate = semantic_target_quality_report(
        "main.py:calculate",
        ranked_candidates=["main.py:calculate"],
        source_evidence=["main.py:calculate"],
        selection_reason="pure transform candidate",
    )
    provider = semantic_target_quality_report(
        "api.py:list_provider_capabilities",
        ranked_candidates=["api.py:list_provider_capabilities"],
        source_evidence=["api.py:list_provider_capabilities"],
    )
    mock_wrapper = semantic_target_quality_report(
        "src/pytest_mock/plugin.py:assert_has_calls_wrapper",
        ranked_candidates=["src/pytest_mock/plugin.py:assert_has_calls_wrapper"],
        source_evidence=["src/pytest_mock/plugin.py:assert_has_calls_wrapper"],
        selection_reason="pure transform candidate",
    )

    assert calculate["status"] == "strong"
    assert provider["status"] == "strong"
    assert mock_wrapper["status"] == "strong"


def test_semantic_target_quality_accepts_job_handlers_and_business_value_transforms():
    handler = semantic_target_quality_report(
        "worker.py:handle_job",
        ranked_candidates=["worker.py:handle_job"],
        source_evidence=["worker.py:handle_job"],
        selection_reason="central flow node with subsystem-level evidence",
    )
    business = semantic_target_quality_report(
        "main.py:price_item",
        ranked_candidates=["main.py:price_item"],
        source_evidence=["main.py:price_item"],
        selection_reason="pure transform candidate",
    )

    assert handler["status"] == "strong"
    assert handler["score"] >= 92
    assert business["status"] == "strong"
    assert business["score"] >= 92


def test_semantic_target_quality_demotes_legacy_batch_orchestrator():
    report = semantic_target_quality_report(
        "legacy.py:legacy_process_all",
        ranked_candidates=["legacy.py:legacy_process_all"],
        source_evidence=["legacy.py:legacy_process_all"],
        selection_reason="broad function can anchor a meaningful first slice",
    )

    assert report["status"] in {"suspicious", "poor"}
    assert "too broad" in " ".join(report["reasons"])


def test_semantic_target_quality_demotes_health_probe():
    report = semantic_target_quality_report(
        "api.py:health",
        ranked_candidates=["api.py:health"],
        source_evidence=["api.py:health"],
    )

    assert report["status"] in {"suspicious", "poor"}


def test_semantic_target_quality_accepts_holdout_domain_contracts():
    cases = [
        ("src/pipx/commands/inject.py:inject_dep", "first-slice target"),
        ("rich/pretty.py:traverse", "first-slice target"),
        ("starlette/authentication.py:requires", "first-slice target"),
    ]
    for target, reason in cases:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason=reason,
        )
        assert report["status"] == "strong", target
        assert report["score"] >= 92, target

    framework_response = semantic_target_quality_report(
        "src/flask/app.py:make_response",
        ranked_candidates=["src/flask/app.py:make_response"],
        source_evidence=["src/flask/app.py:make_response"],
        selection_reason="pure transform candidate",
    )
    assert framework_response["status"] == "strong"
    assert framework_response["score"] >= 92

    response = semantic_target_quality_report(
        "app.py:make_response",
        ranked_candidates=["app.py:make_response"],
        source_evidence=["app.py:make_response"],
        selection_reason="pure transform candidate",
    )
    assert response["status"] == "acceptable"
    assert response["score"] < 85


def test_semantic_target_quality_accepts_second_holdout_domain_contracts():
    cases = [
        ("aiohttp/client.py:_ws_connect", "first-slice target"),
        ("httpie/core.py:program", "first-slice target"),
        ("pydantic/_internal/_model_construction.py:__new__", "first-slice target"),
        ("src/tox/session/cmd/run/common.py:_do_queue_and_wait", "first-slice target"),
        ("src/trio/_core/_run.py:unrolled_run", "first-slice target"),
    ]
    for target, reason in cases:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason=reason,
        )
        assert report["status"] == "strong", target
        assert report["score"] >= 92, target


def test_semantic_target_quality_accepts_scientific_and_media_contracts():
    cases = [
        "numpy/lib/_function_base_impl.py:_quantile",
        "pandas/core/construction.py:array",
        "src/PIL/Image.py:convert",
        "sklearn/calibration.py:calibration_curve",
    ]
    for target in cases:
        report = semantic_target_quality_report(
            target,
            ranked_candidates=[target],
            source_evidence=[target],
            selection_reason="ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
        )
        assert report["status"] == "strong", target
        assert report["score"] >= 92, target


def test_semantic_target_quality_accepts_profiled_asgi_runtime_wrapper():
    report = semantic_target_quality_report(
        "sentry_sdk/integrations/asgi.py:_run_app",
        ranked_candidates=["sentry_sdk/integrations/asgi.py:_run_app"],
        source_evidence=["sentry_sdk/integrations/asgi.py:_run_app"],
        selection_reason="ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
    )

    assert report["status"] == "strong"
    assert report["score"] >= 92
    assert "ASGI app wrapper" in " ".join(report["reasons"])


def test_semantic_target_quality_caps_unprofiled_generic_library_contracts():
    target = "project/core/parser.py:parse_unknown_record"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="deterministic parser/normalizer/validator shape",
    )

    assert report["status"] == "acceptable"
    assert report["score"] == 84
    assert "unprofiled generic library contract" in " ".join(report["reasons"])


def test_semantic_target_quality_caps_unprofiled_shape_only_strong_scores():
    target = "src/worker/runtime.py:build_unknown_tracer"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="deterministic parser/normalizer/validator shape",
    )

    assert report["status"] == "acceptable"
    assert report["score"] == 84
    assert "shape alone" in " ".join(report["reasons"])


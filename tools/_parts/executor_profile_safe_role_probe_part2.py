from __future__ import annotations

def _run_case(
    root: Path, work_root: Path, row: dict[str, Any], *, project_stratum: str,
    cli_interface: str, web_interface: str, provider_interface: str,
    stateful_interface: str,
    async_interface: str,
    io_interface: str,
    framework_interface: str,
) -> dict[str, Any]:
    target_file = f"trial_{row['symbol']}.py"
    project_dir = _case_project(
        work_root, row, target_file=target_file,
        cli_interface=cli_interface, web_interface=web_interface,
        provider_interface=provider_interface,
        stateful_interface=stateful_interface,
        async_interface=async_interface,
        io_interface=io_interface,
        framework_interface=framework_interface,
    )
    source_path = project_dir / target_file
    source_before = source_path.read_text(encoding="utf-8")
    target = f"{target_file}:{row['symbol']}"
    spec = build_technical_spec(architecture_decision=_adr(target, row))
    plan = build_implementation_plan(technical_spec=spec)
    test_plan = build_test_plan(technical_spec=spec, implementation_plan=plan)
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )
    patch = _read_json(result.get("patch_package_path"))
    test_result = _read_json(result.get("test_result_path"))
    control_result = run_test_result(
        root=root,
        project_dir=project_dir,
        source_project_dir=project_dir,
        implementation_plan=plan,
        test_plan=test_plan,
        execution_dir=Path(str(result["execution_dir"])) / "identity_control",
        run_verification=True,
        max_commands=3,
    )
    enforce_prepared_patch_acceptance(control_result, dict(patch.get("patch_synthesis") or {}), plan)
    cli_evidence = None
    if project_stratum == "cli_local_tool":
        cli_evidence = {
            "patched": _cli_check(Path(str(result["execution_project"])), row, cli_interface),
            "identity_control": _cli_check(project_dir, row, cli_interface),
        }
        if cli_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if cli_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    web_evidence = None
    if project_stratum == "web_api_middleware":
        web_evidence = {
            "patched": _web_check(Path(str(result["execution_project"])), row, web_interface),
            "identity_control": _web_check(project_dir, row, web_interface),
        }
        if web_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if web_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    provider_evidence = None
    if project_stratum == "sdk_provider_integration":
        provider_evidence = {
            "patched": _provider_check(
                Path(str(result["execution_project"])), row, provider_interface
            ),
            "identity_control": _provider_check(project_dir, row, provider_interface),
        }
        if provider_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if provider_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    stateful_evidence = None
    if project_stratum == "stateful_service_database":
        stateful_evidence = {
            "patched": _stateful_check(
                Path(str(result["execution_project"])), row, stateful_interface
            ),
            "identity_control": _stateful_check(project_dir, row, stateful_interface),
        }
        if stateful_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if stateful_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    async_evidence = None
    if project_stratum == "async_worker_scheduler":
        async_evidence = {
            "patched": _async_check(
                Path(str(result["execution_project"])), row, async_interface
            ),
            "identity_control": _async_check(project_dir, row, async_interface),
        }
        if async_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if async_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    io_evidence = None
    if project_stratum == "external_process_io":
        io_evidence = {
            "patched": _io_check(Path(str(result["execution_project"])), row, io_interface),
            "identity_control": _io_check(project_dir, row, io_interface),
        }
        if io_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if io_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    framework_evidence = None
    if project_stratum == "framework_plugin_build":
        framework_evidence = {
            "patched": _framework_check(
                Path(str(result["execution_project"])), row, framework_interface
            ),
            "identity_control": _framework_check(project_dir, row, framework_interface),
        }
        if framework_evidence["patched"]["status"] != "passed":
            test_result["status"] = "failed"
        if framework_evidence["identity_control"]["status"] != "passed":
            control_result["status"] = "failed"
    passing_review = build_review_findings(
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        test_result=test_result,
    )
    failing_review = build_review_findings(
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        test_result=control_result,
    )
    quality = evaluate_transformation_case(
        expected_profile=str(row["profile_id"]),
        expected_operator=str(row["operator_id"]),
        source_before=source_before,
        source_after=source_path.read_text(encoding="utf-8"),
        technical_spec=spec,
        result=result,
        patch_package=patch,
        test_result=test_result,
    )
    stub_admission = inspect_generated_function_stubs(
        original_project=project_dir,
        sandbox_project=Path(str(result["execution_project"])),
        patch=patch,
    )
    role_evidence = _role_evidence(
        row=row,
        architecture_decision=_adr(target, row),
        technical_spec=spec,
        plan=plan,
        test_plan=test_plan,
        test_result=test_result,
        control_result=control_result,
        passing_review=passing_review,
        failing_review=failing_review,
        transformation_quality=quality,
        cli_evidence=cli_evidence,
        web_evidence=web_evidence,
        provider_evidence=provider_evidence,
        stateful_evidence=stateful_evidence,
        async_evidence=async_evidence,
        io_evidence=io_evidence,
        framework_evidence=framework_evidence,
        stub_admission=stub_admission,
    )
    accepted = quality["status"] == "ok" and stub_admission["status"] == "passed" and all(
        evidence["score"] == 10.0 for evidence in role_evidence.values()
    )
    return {
        "project": row["project"],
        "source_target": row["source_target"],
        **quality,
        "status": "ok" if accepted else "needs_review",
        "role_scores": {role: evidence["score"] for role, evidence in role_evidence.items()},
        "role_evidence": role_evidence,
        "programmer_evidence": {
            "transformation_evaluated": True,
            "checks": quality["checks"],
        },
        "source_lineage": row.get("source_lineage"),
        "generated_function_stub_admission": stub_admission,
        "project_classification": {
            "schema_version": "role_project_classification.v1",
            "policy_version": load_role_project_type_policy()["classification_version"],
            "project_stratum": project_stratum,
            "project_archetype": _benchmark_archetype(project_stratum),
            "contract_family": (
                "argv_stdout_transform" if cli_evidence
                else "http_json_endpoint" if web_evidence
                else "provider_fixture_adapter" if provider_evidence
                else "sqlite_state_transition" if stateful_evidence
                else "async_execution_boundary" if async_evidence
                else "external_io_boundary" if io_evidence
                else "framework_extension_artifact_boundary" if framework_evidence
                else "llm_message_tool_response_transform" if project_stratum == "llm_multi_agent"
                else "pure_transform"
            ),
            "project_shape": "single_callable_sandbox",
            "project_subtype": (
                f"{cli_interface}_stdout_json" if cli_evidence
                else f"{web_interface}_http_json" if web_evidence
                else f"{provider_interface}_provider_response" if provider_evidence
                else f"{stateful_interface}_sqlite" if stateful_evidence
                else f"{async_interface}_async" if async_evidence
                else f"{io_interface}_boundary" if io_evidence
                else f"{framework_interface}_framework" if framework_evidence
                else f"operator:{row['operator_id']}"
            ),
            "risk_profiles": (
                ["deterministic", "provider_llm"] if provider_evidence
                else ["deterministic", "stateful"] if stateful_evidence
                else ["deterministic", "concurrent"] if async_evidence
                else ["deterministic", "filesystem", "subprocess"] if io_evidence
                else ["deterministic", "filesystem"] if framework_evidence
                else ["deterministic", "provider_llm"] if project_stratum == "llm_multi_agent"
                else ["deterministic"]
            ),
        },
        "control_test_result_status": control_result.get("status"),
        "control_acceptance_status": dict(control_result.get("executable_acceptance_result") or {}).get("status"),
        "passing_review_recommendation": passing_review.get("recommendation"),
        "failing_review_recommendation": failing_review.get("recommendation"),
        "cli_evidence": cli_evidence,
        "web_evidence": web_evidence,
        "provider_evidence": provider_evidence,
        "stateful_evidence": stateful_evidence,
        "async_evidence": async_evidence,
        "io_evidence": io_evidence,
        "framework_evidence": framework_evidence,
        "executor_status": result.get("status"),
        "source_code_changes": bool(result.get("source_code_changes")),
    }


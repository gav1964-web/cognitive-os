from __future__ import annotations

def write_report(root: Path, report: dict[str, Any], label: str) -> dict[str, str]:
    report_dir = root / "artifacts" / "field_trials"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = report_dir / f"{label}_{stamp}.json"
    md_path = report_dir / f"{label}_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    return {"report_path": json_path.as_posix(), "markdown_path": md_path.as_posix()}


def _chain_checks(
    adr: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
    target_chain: dict[str, str],
    forbidden: list[str],
    executor: dict[str, Any],
    run_executor: bool,
) -> list[dict[str, Any]]:
    adr_targets = set(target_chain.get("adr_targets", []))
    spec_target = str(target_chain.get("spec_target", ""))
    implementation_target = target_chain.get("implementation_target", "")
    test_target = target_chain.get("test_target", "")
    review_target = target_chain.get("review_target", "")
    binding = dict(plan.get("contract_binding", {}))
    coverage = dict(review.get("coverage_assessment", {}))
    checks = [
        _check("adr_artifact_ready", adr.get("artifact_type") == "ArchitectureDecisionRecord" and adr.get("role") == producer_for_artifact_type("ArchitectureDecisionRecord")),
        _check("spec_artifact_ready", spec.get("artifact_type") == "TechnicalSpec" and spec.get("role") == producer_for_artifact_type("TechnicalSpec")),
        _check("implementation_artifact_ready", plan.get("artifact_type") == "ImplementationPlan" and plan.get("role") == producer_for_artifact_type("ImplementationPlan")),
        _check("test_artifact_ready", test_plan.get("artifact_type") == "TestPlan" and test_plan.get("role") == producer_for_artifact_type("TestPlan")),
        _check("review_artifact_ready", review.get("artifact_type") == "ReviewFindings" and review.get("role") == producer_for_artifact_type("ReviewFindings")),
        _check("architecture_has_traceability", bool(adr.get("traceability")) and bool(adr.get("source_context"))),
        _check("spec_has_contract", bool(spec_target) and bool(spec.get("source_evidence")) and bool(spec.get("acceptance_criteria"))),
        _check("spec_target_is_advised_by_adr", bool(spec_target) and _target_is_advised(spec_target, adr_targets)),
        _check("target_chain_preserved", bool(spec_target) and spec_target == implementation_target == test_target == review_target),
        _check("implementation_bound_to_spec", binding.get("binding_status") in {"bound_to_extraction_contract", "bound_to_product_contract"}),
        _check("implementation_scope_bounded", list(plan.get("writable_scope", [])) == [implementation_target] and bool(plan.get("patch_scope"))),
        _check("tester_covers_contract", bool(test_plan.get("contract_test_matrix")) and bool(test_plan.get("negative_tests")) and coverage.get("target_covered") is True),
        _check("review_conformance_passed", review.get("conformance_status") == "passed"),
        _check("review_has_no_contract_violations", not review.get("contract_violations")),
        _check("review_has_no_architecture_drift", not review.get("architecture_drift")),
        _check("forbidden_sources_clean", not forbidden and not review.get("forbidden_actions_observed")),
    ]
    if run_executor:
        checks.extend(
            [
                _check("executor_completed", executor.get("executor_status") == "ok"),
                _check("patch_package_prepared", executor.get("patch_package_status") == "prepared"),
                _check("test_result_ok", executor.get("test_result_status") == "ok"),
                _check("executable_acceptance_passed", executor.get("executable_acceptance") == "passed"),
                _check("executable_acceptance_callable", executor_evidence_ready(executor)),
                _check("executor_kept_source_clean", executor.get("source_code_changes") is False),
            ]
        )
    return checks


def _target_is_advised(target: str, advised_targets: set[str]) -> bool:
    if target in advised_targets:
        return True
    target_path, separator, target_symbol = target.replace("\\", "/").partition(":")
    if not separator:
        return False
    target_leaf = target_symbol.rsplit(".", 1)[-1]
    return any(
        advised_path == target_path and advised_symbol.rsplit(".", 1)[-1] == target_leaf
        for advised in advised_targets
        for advised_path, advised_separator, advised_symbol in [advised.replace("\\", "/").partition(":")]
        if advised_separator
    )


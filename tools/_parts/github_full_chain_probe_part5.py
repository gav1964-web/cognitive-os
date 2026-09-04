from __future__ import annotations

def _run_executor(
    *,
    root: Path,
    project_dir: Path,
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    run_executor: bool,
    run_verification: bool,
) -> dict[str, Any]:
    if not run_executor:
        return _executor_not_run()
    result = run_programmer_executor(root=root, project_dir=project_dir, technical_spec=spec, implementation_plan=plan, test_plan=test_plan, run_verification=run_verification, apply_source=False)
    test_result = _read_json(result.get("test_result_path"))
    executable = dict(test_result.get("executable_acceptance_result") or {})
    acceptance = dict(executable.get("summary") or {})
    patch = _read_json(result.get("patch_package_path"))
    synthesis = dict(patch.get("patch_synthesis") or {})
    return {
        "executor_status": result.get("status"),
        "execution_dir": result.get("execution_dir"),
        "patch_package_status": patch.get("status"),
        "patch_synthesis_status": synthesis.get("status"),
        "patch_synthesis_reason": synthesis.get("reason"),
        "test_result_status": test_result.get("status"),
        "executable_acceptance": executable.get("status"),
        "callable_harness_count": acceptance.get("callable_harness_count"),
        "acceptance_signal": acceptance.get("signal_strength"),
        "acceptance_skipped_reasons": acceptance.get("skipped_reason_counts"),
        "acceptance_skipped_targets": acceptance.get("skipped_targets"),
        "source_code_changes": bool(result.get("source_code_changes")),
    }


def _executor_not_run() -> dict[str, Any]:
    keys = ["patch_package_status", "patch_synthesis_status", "test_result_status", "executable_acceptance", "callable_harness_count", "acceptance_signal", "acceptance_skipped_reasons", "acceptance_skipped_targets"]
    return {"executor_status": "not_run", **{key: None for key in keys}, "source_code_changes": False}


def _read_json(path: object) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(str(path))
    return json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}


def _selected_effect_mode(spec: dict[str, Any]) -> str:
    contract = dict(spec.get("extraction_contract") or {})
    structural = dict(contract.get("structural_evidence") or {})
    declared = contract.get("side_effects")
    values: list[str] = []
    if isinstance(declared, dict):
        for value in declared.values():
            values.extend(value if isinstance(value, list) else [value] if value else [])
    elif isinstance(declared, list):
        values.extend(declared)
    values.extend(structural.get("observed_side_effects") or [])
    effects = {str(value).lower() for value in values if value}
    if not effects:
        return "pure"
    read_markers = {"filesystem_read", "file_read", "read_file"}
    if effects <= read_markers:
        return "filesystem_read"
    return "sandbox_only"


def _target_chain(
    adr: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    first_slice = dict(adr.get("first_slice_contract", {}))
    brief = dict(adr.get("spec_writer_brief", {}))
    adr_targets = [
        str(item)
        for item in [
            *list(first_slice.get("targets", [])),
            *list(brief.get("files_or_symbols", [])),
        ]
        if item
    ]
    return {
        "adr_targets": sorted(set(adr_targets)),
        "spec_target": str(dict(spec.get("extraction_contract", {})).get("candidate") or ""),
        "implementation_target": str(dict(plan.get("implementation_target", {})).get("candidate") or ""),
        "test_target": str(dict(test_plan.get("test_target", {})).get("candidate") or ""),
        "review_target": str(dict(review.get("review_target", {})).get("candidate") or ""),
    }


def _forbidden_sources(
    target_chain: dict[str, str],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    strategy = dict(test_plan.get("test_strategy", {}))
    values = [
        *[item for value in target_chain.values() for item in (value if isinstance(value, list) else [value])],
        *[str(item) for item in plan.get("patch_scope", [])],
        *[str(item) for item in plan.get("writable_scope", [])],
        *[str(item) for item in strategy.get("writable_scope", [])],
        *[str(item) for item in dict(review.get("coverage_assessment", {})).get("writable_scope", [])],
    ]
    return [value for value in values if _is_forbidden_source(value)]


def _blocked_reason(project_report: dict[str, Any]) -> str:
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    blocked = [str(item) for item in plan.get("blocked_by", [])]
    return "no_safe_python_candidate" if "no_safe_python_candidate" in blocked else ""


def _is_forbidden_source(value: str) -> bool:
    return is_context_only_implementation_target(value)


def _git_porcelain(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "__git_status_unavailable__"
    return "\n".join(
        line
        for line in result.stdout.splitlines()
        if not _ephemeral_python_cache_status(line)
    ).strip()


def _ephemeral_python_cache_status(line: str) -> bool:
    path = line[3:].strip().replace("\\", "/") if len(line) > 3 else ""
    return "/__pycache__/" in f"/{path}" or path.endswith(".pyc")


def _check(code: str, passed: bool) -> dict[str, Any]:
    return {"code": code, "passed": bool(passed)}


if __name__ == "__main__":
    raise SystemExit(main())

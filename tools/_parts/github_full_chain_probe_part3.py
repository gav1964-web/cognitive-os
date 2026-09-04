from __future__ import annotations

def _recognition_controlled_stop(
    *, project_dir: Path, recognition: dict[str, Any], dirty_before: list[str]
) -> dict[str, Any]:
    facade = sys.modules.get("tools.github_full_chain_probe")
    git_porcelain = getattr(facade, "_git_porcelain", _git_porcelain)
    dirty_after = git_porcelain(project_dir)
    route = dict(recognition.get("pilot_route") or {})
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": "blocked_ok",
        "quality_score": CONTROLLED_BLOCK_SCORE,
        "selected_target_quality": {"score": 0.0, "status": "not_run_after_recognition"},
        "project_classification": dict(recognition.get("classification") or {}),
        "project_recognition": recognition,
        "effect_mode": "sandbox_only",
        "blocked_reason": "early_project_recognition_stop",
        "target_chain": {},
        "artifact_status": {"project_recognition": "ProjectRecognitionDecision"},
        "binding_status": "not_run_after_recognition",
        "conformance_status": "controlled_stop",
        "contract_violations": 0,
        "architecture_drift": 0,
        "executor": _executor_not_run(),
        "execution_reselection": {"status": "not_run", "iteration_count": 0, "history": []},
        "forbidden_sources": [],
        "llm_invoked": False,
        "source_project_dirty_before": bool(dirty_before),
        "source_project_dirty_after": bool(dirty_after),
        "source_code_changes": dirty_before != dirty_after,
        "failed_checks": [],
        "recognition_blocking_reasons": list(route.get("blocking_reasons") or []),
    }


def _rerun_after_execution_reselection(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    project_report: dict[str, Any],
    revised_adr: dict[str, Any],
    run_verification: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    def replace_adr(artifact: dict[str, Any]) -> dict[str, Any]:
        return revised_adr if artifact.get("artifact_type") == "ArchitectureDecisionRecord" else artifact

    artifacts = run_configured_role_prefix(
        goal=goal,
        project_report=project_report,
        until_artifact_type="ReviewFindings",
        artifact_transform=replace_adr,
        reselection_triggers=set(),
    )
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    plan = artifact_by_type(artifacts, "ImplementationPlan")
    test_plan = artifact_by_type(artifacts, "TestPlan")
    executor = _run_executor(
        root=root,
        project_dir=project_dir,
        spec=spec,
        plan=plan,
        test_plan=test_plan,
        run_executor=True,
        run_verification=run_verification,
    )
    return artifacts, executor



from __future__ import annotations

def _run_case(
    project_dir: Path,
    *,
    root: Path | None = None,
    run_executor: bool = False,
    run_verification: bool = False,
    recognition_profile: dict[str, Any] | None = None,
    stop_outside_recognition_profile: bool = False,
) -> dict[str, Any]:
    root = root or Path.cwd()
    facade = sys.modules.get("tools.github_full_chain_probe")
    git_porcelain = getattr(facade, "_git_porcelain", _git_porcelain)
    project_analyzer = getattr(facade, "analyze_role_project", analyze_role_project)
    role_prefix = getattr(facade, "run_configured_role_prefix", run_configured_role_prefix)
    language_scope = _primary_language_scope(project_dir)
    if language_scope.get("status") == "out_of_scope":
        return {
            "project": project_dir.name,
            "project_dir": project_dir.as_posix(),
            "status": "out_of_scope",
            "quality_score": 0.0,
            "blocked_reason": language_scope.get("reason") or "unsupported_primary_language_for_python_full_chain",
            "target_chain": {},
            "artifact_status": {},
            "binding_status": None,
            "conformance_status": None,
            "contract_violations": 0,
            "architecture_drift": 0,
            "executor": _executor_not_run(),
            "forbidden_sources": [],
            "llm_invoked": False,
            "source_project_dirty_before": bool(git_porcelain(project_dir)),
            "source_project_dirty_after": bool(git_porcelain(project_dir)),
            "source_code_changes": False,
            "failed_checks": [],
        }

    dirty_before = git_porcelain(project_dir)
    case_goal = f"GitHub full-chain probe for {project_dir.name}"
    project_report = project_analyzer(
        root=root, project_dir=project_dir, goal=case_goal
    )["project_map_report"]
    recognition = recognize_project(
        project=project_dir.name,
        project_report=project_report,
        profile=recognition_profile,
    )
    project_report = attach_project_recognition(project_report, recognition)
    if (
        stop_outside_recognition_profile
        and dict(recognition.get("pilot_route") or {}).get("status") != "eligible_for_full_chain"
    ):
        return _recognition_controlled_stop(
            project_dir=project_dir,
            recognition=recognition,
            dirty_before=dirty_before,
        )
    artifacts = role_prefix(
        goal=case_goal,
        project_report=project_report,
        until_artifact_type="ReviewFindings",
    )
    adr = artifact_by_type(artifacts, "ArchitectureDecisionRecord")
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    plan = artifact_by_type(artifacts, "ImplementationPlan")
    test_plan = artifact_by_type(artifacts, "TestPlan")
    review = artifact_by_type(artifacts, "ReviewFindings")
    classification = dict(recognition.get("classification") or {})

    blocked_reason = _blocked_reason(project_report)
    target_chain = _target_chain(adr, spec, plan, test_plan, review)
    forbidden = _forbidden_sources(target_chain, plan, test_plan, review)
    executor = _run_executor(
        root=root,
        project_dir=project_dir,
        spec=spec,
        plan=plan,
        test_plan=test_plan,
        run_executor=run_executor,
        run_verification=run_verification,
    )
    execution_feedback = {"status": "not_run", "iteration_count": 0, "history": []}
    if run_executor:
        artifacts, executor, execution_feedback = close_configured_execution_feedback(
            artifacts=artifacts,
            executor=executor,
            project_report=project_report,
            rerun=lambda revised: _rerun_after_execution_reselection(
                root=root,
                project_dir=project_dir,
                goal=case_goal,
                project_report=project_report,
                revised_adr=revised,
                run_verification=run_verification,
            ),
        )
        adr = artifact_by_type(artifacts, "ArchitectureDecisionRecord")
        spec = artifact_by_type(artifacts, "TechnicalSpec")
        plan = artifact_by_type(artifacts, "ImplementationPlan")
        test_plan = artifact_by_type(artifacts, "TestPlan")
        review = artifact_by_type(artifacts, "ReviewFindings")
        target_chain = _target_chain(adr, spec, plan, test_plan, review)
        forbidden = _forbidden_sources(target_chain, plan, test_plan, review)
    role_artifacts = {
        "project_map_report": project_report,
        "architecture_decision": adr,
        "technical_spec": spec,
    }
    semantic_quality = evaluate_framework_plugin_role_semantics(
        project_report=project_report,
        architecture_decision=adr,
        technical_spec=spec,
        classification=classification,
        goal=case_goal,
        executor=executor,
    )
    checks = _chain_checks(adr, spec, plan, test_plan, review, target_chain, forbidden, executor, run_executor)
    if classification.get("project_stratum") == "framework_plugin_build":
        checks.append(_check(
            "framework_role_semantics_passed",
            semantic_quality.get("status") == "passed",
        ))
    target_quality = selected_target_quality(spec, project_dir.name)
    quality = bounded_quality_score(checks, target_quality)
    executor_ready = not run_executor or executor_evidence_ready(executor)
    if run_executor and not executor_ready:
        quality = min(quality, META_ONLY_SCORE_CAP)
    status = "ok" if quality >= READY_THRESHOLD and not forbidden and executor_ready else "needs_review"
    if (
        classification.get("project_stratum") == "framework_plugin_build"
        and semantic_quality.get("status") != "passed"
    ):
        quality = min(quality, META_ONLY_SCORE_CAP)
        status = "needs_review"
    if is_controlled_block(spec, plan, forbidden):
        status = "blocked_ok"
        quality = CONTROLLED_BLOCK_SCORE
        checks = [{"code": "controlled_no_safe_candidate_block", "passed": True}]
    dirty_after = _git_porcelain(project_dir)
    return {
        "project": project_dir.name,
        "project_dir": project_dir.as_posix(),
        "status": status,
        "quality_score": quality,
        "selected_target_quality": target_quality,
        "project_classification": classification,
        "project_recognition": recognition,
        "effect_mode": _selected_effect_mode(spec),
        "blocked_reason": blocked_reason,
        "target_chain": target_chain,
        "artifact_status": {
            "architecture_decision": adr.get("artifact_type"),
            "technical_spec": spec.get("artifact_type"),
            "implementation_plan": plan.get("artifact_type"),
            "test_plan": test_plan.get("artifact_type"),
            "review_findings": review.get("artifact_type"),
        },
        "role_artifacts": role_artifacts,
        "role_artifact_digests": {
            name: artifact_digest(artifact)
            for name, artifact in role_artifacts.items()
        },
        "role_semantic_quality": semantic_quality,
        "binding_status": dict(plan.get("contract_binding", {})).get("binding_status"),
        "conformance_status": review.get("conformance_status"),
        "contract_violations": len(review.get("contract_violations", [])),
        "architecture_drift": len(review.get("architecture_drift", [])),
        "executor": executor,
        "generated_function_stub_admission": dict(
            executor.get("generated_function_stub_admission") or {}
        ),
        "execution_reselection": execution_feedback,
        "forbidden_sources": sorted(set(forbidden)),
        "llm_invoked": False,
        "source_project_dirty_before": bool(dirty_before),
        "source_project_dirty_after": bool(dirty_after),
        "source_code_changes": dirty_before != dirty_after,
        "failed_checks": [check for check in checks if not check["passed"]],
    }


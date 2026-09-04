import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_exception_pickle_docs_track_active_kb_evidence() -> None:
    kb = json.loads(
        (ROOT / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = kb["post_promotion_application_evidence"]
    count_markers = [
        f"applied={evidence['applied_count']}",
        f"blocked={evidence['blocked_count']}",
    ]
    artifact_markers = [
        Path(evidence["latest_applied_report"]).name,
        Path(evidence["latest_blocker_intelligence"]).name,
        evidence["latest_applied_project"],
        evidence["latest_applied_target"].split(":")[-1],
    ]

    for name in (
        "README.md",
        "MVP_STATUS.md",
        "KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md",
        "COGNITIVE_OS_TECHNICAL_BASELINE.md",
    ):
        text = _read(name)
        for marker in count_markers:
            assert marker in text
        for marker in artifact_markers:
            assert marker in text


def test_exception_pickle_docs_track_derived_message_audit() -> None:
    kb = json.loads(
        (ROOT / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json").read_text(
            encoding="utf-8"
        )
    )
    audit = kb["post_promotion_application_evidence"]["blocker_intelligence"]["derived_message_audit"]
    markers = [
        Path(
            kb["post_promotion_application_evidence"]["blocker_intelligence"][
                "latest_derived_message_audit"
            ]
        ).name,
        f"{audit['case_count']} derived-message cases",
    ]
    lane_summary = audit["lane_summary"]
    if "derived_message_ready_replay" in lane_summary:
        markers.append(f"{lane_summary['derived_message_ready_replay']} ready replay cases")
    if "derived_message_import_isolation_first" in lane_summary:
        markers.append(
            f"{lane_summary['derived_message_import_isolation_first']} import-isolation-first cases"
        )
    if "derived_message_patch_shape_first" in lane_summary:
        markers.append(
            f"{lane_summary['derived_message_patch_shape_first']} patch-shape-first cases"
        )

    for name in (
        "README.md",
        "MVP_STATUS.md",
        "KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md",
        "COGNITIVE_OS_TECHNICAL_BASELINE.md",
    ):
        text = _read(name)
        for marker in markers:
            assert marker in text


def test_exception_pickle_docs_track_derived_import_audit() -> None:
    kb = json.loads(
        (ROOT / "knowledge/role_knowledge/exception_pickle_reconstruction_patterns.json").read_text(
            encoding="utf-8"
        )
    )
    audit = kb["post_promotion_application_evidence"]["blocker_intelligence"]["derived_import_audit"]
    markers = [
        Path(
            kb["post_promotion_application_evidence"]["blocker_intelligence"][
                "latest_derived_import_audit"
            ]
        ).name,
        f"{audit['case_count']} derived import-isolation cases",
    ]
    lane_summary = audit["lane_summary"]
    if "derived_import_direct_file_fallback_candidate" in lane_summary:
        markers.append(
            f"{lane_summary['derived_import_direct_file_fallback_candidate']} direct-file fallback candidates"
        )
    if "derived_import_target_stub_candidate" in lane_summary:
        markers.append(
            f"{lane_summary['derived_import_target_stub_candidate']} target-stub candidates"
        )
    if "derived_import_metadata_side_effect" in audit["lane_summary"]:
        markers.append(
            f"{audit['lane_summary']['derived_import_metadata_side_effect']} metadata side-effect candidate"
        )

    for name in (
        "README.md",
        "MVP_STATUS.md",
        "KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md",
        "COGNITIVE_OS_TECHNICAL_BASELINE.md",
    ):
        text = _read(name)
        for marker in markers:
            assert marker in text


def test_readme_tracks_runtime_role_artifact_order() -> None:
    readme = _read("README.md")

    assert (
        "Project Analyzer -> Architect -> SpecWriter -> Implementer Planner -> "
        "Tester (TestPlan) -> Sandbox Programmer (PatchPackage/TestResult) -> Reviewer"
    ) in readme


def test_core_docs_track_controlled_recovery_contract() -> None:
    baseline = _read("COGNITIVE_OS_TECHNICAL_BASELINE.md")
    readme = _read("README.md")

    route = "Reviewer -> Researcher -> Architect -> Developer -> Tester -> Architect"
    assert route in baseline
    assert route in readme
    for symbol in ("normalize_record", "serialize_json", "parse_json", "split_lines"):
        assert symbol in baseline


def test_status_keeps_measurement_axes_separate() -> None:
    readme = _read("README.md")
    status = _read("MVP_STATUS.md")

    assert "Readiness, role-by-project-type maturity, and production confidence" in readme
    assert "aggregate readiness `1.0`" in status
    assert "8 of 8 measured roles MVP-ready" in status
    assert "production-confidence scores" in status


def test_docs_keep_pilot_and_semantic_boundaries_fail_closed() -> None:
    readme = _read("README.md")
    summary = _read("KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md")

    assert "pilot remains blocked" in readme
    assert "all four current families remain blocked from Developer handoff" in readme
    assert "source apply запрещён" in summary


def test_docs_track_project_development_boundary() -> None:
    readme = _read("README.md")
    baseline = _read("COGNITIVE_OS_TECHNICAL_BASELINE.md")
    summary = _read("KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md")

    for text in (readme, baseline):
        assert "ProjectDevelopmentDiagnosis" in text
        assert "ProjectDevelopmentOutcomeContract" in text
        assert "needs_replanning" in text
    assert "не только planning/decision layer" in summary
    assert "extract_json_dumps_helper" in summary
    assert "extract_json_loads_helper" in summary
    assert "extract_splitlines_helper" in summary
    assert "extract_append_mapping_helper" in summary
    assert "project_development_20260828T070645103118Z.json" in summary
    assert "project_development_20260828T070723270674Z.json" in summary
    assert "project_development_20260828T072338364901Z.json" in summary
    assert "project_development_20260828T072433082449Z.json" in summary
    assert "project_development_20260828T080840365016Z.json" in summary
    assert "project_development_20260828T080915669163Z.json" in summary
    assert "project_development_20260828T083944554908Z.json" in summary
    assert "project_development_20260828T084003587919Z.json" in summary
    assert "ProjectDevelopmentExecutionFeedback" in summary
    assert "project_development_20260828T090705601690Z.json" in summary
    assert "project_development_20260828T090747254502Z.json" in summary
    assert "ProjectDevelopmentResearchHypothesis" in summary
    assert "ProjectDevelopmentArchitectFeedbackDecision" in summary
    assert "ProjectDevelopmentFeedbackContinuation" in summary
    assert "project_development_20260828T093240287559Z.json" in summary
    assert "project_development_20260828T093325940127Z.json" in summary
    assert "ProjectDevelopmentReplanRevision" in summary
    assert "project_development_20260828T100823826409Z.json" in summary
    assert "project_development_20260828T100905579561Z.json" in summary
    assert "ProjectDevelopmentBoundedExperimentProposal" in summary
    assert "ProjectDevelopmentBoundedExperimentAdmission" in summary
    assert "project_development_20260828T104947964126Z.json" in summary
    assert "project_development_20260828T105018631041Z.json" in summary
    assert "ProjectDevelopmentBoundedExperimentEvidence" in summary
    assert "ProjectDevelopmentArchitectEvidenceDecision" in summary
    assert "project_development_20260828T111911887620Z.json" in summary
    assert "project_development_20260828T111943104093Z.json" in summary
    assert "project_development_20260828T113702427711Z.json" in summary
    assert "project_development_20260828T113733891395Z.json" in summary
    assert "ProjectDevelopmentImplementationApprovalRequest" in summary
    assert "ProjectDevelopmentHumanApprovalDecision" in summary
    assert "ProjectDevelopmentImplementationApprovalValidation" in summary
    assert "ProjectDevelopmentBoundedImplementationCandidate" in summary
    assert "project_development_20260828T115407964184Z.json" in summary
    assert "project_development_20260828T115440020888Z.json" in summary
    assert "ProjectDevelopmentImplementationDesignRequest" in summary
    assert "ProjectDevelopmentImplementationDesignAdmission" in summary
    assert "ProjectDevelopmentImplementationDesign" in summary
    assert "ProjectDevelopmentImplementationDesignValidation" in summary
    assert "project_development_20260831T080044961164Z.json" in summary
    assert "ProjectDevelopmentImplementationAuthorizationRequest" in summary
    assert "ProjectDevelopmentImplementationAuthorizationDecision" in summary
    assert "ProjectDevelopmentImplementationAuthorizationValidation" in summary
    assert "ProjectDevelopmentAuthorizedImplementationResult" in summary
    assert "authorized_implementation_20260831T081035446426Z.json" in summary
    assert "project_development_20260828T120640182121Z.json" in summary
    assert "project_development_20260828T120712767813Z.json" in summary
    assert "project_development_boundary_profiles.json" in summary
    assert "project_development_boundary_interpreter.py" in summary
    assert "cli_local_tool" in summary
    assert "library_pure_transform" in summary
    assert "deferred lane" in summary
    assert "role_foundation_min_field_trial_20260828T130714421779Z.json" in summary


def test_docs_track_bounded_self_development_protocol() -> None:
    readme = _read("README.md")
    baseline = _read("COGNITIVE_OS_TECHNICAL_BASELINE.md")
    status = _read("MVP_STATUS.md")
    summary = _read("KB_COGNITIVE_OS_ARCHITECT_SUMMARY.md")

    for text in (readme, baseline, status, summary):
        assert "SelfDevelopmentChangeProposal" in text
        assert "L0-L4" in text
    assert "unknown target kind" in readme
    assert "L1-sensitive" in baseline
    assert "shadow-only" in status
    assert "self_development_change_policy.json" in summary
    for text in (readme, baseline, status, summary):
        assert "self_development_shadow_trial_20260830T175415849133Z.json" in text
    assert "prospective" in readme
    assert "SelfDevelopmentShadowTrialReport" in baseline
    for text in (readme, baseline, status, summary):
        assert "self_development_prospective_detection_20260831T031558750274Z.json" in text
        assert "waiting_for_evidence" in text
        assert "self_development_corpus_eligibility_20260831T052410743974Z.json" in text
        assert "pytest_plugin_holdout_20260831/holdout_report.json" in text
        assert "SelfDevelopmentCorpusEligibilityIndex" in text
        assert "owned_packaging_build_backend" in text
        assert "ClassificationConsistencyEvidence" in text
    assert "SelfDevelopmentProspectiveDetectionReport" in baseline
    for text in (readme, baseline, status, summary):
        assert "self_development_fresh_blind_trial_20260830T183308224089Z.json" in text
        assert "evidence_exhausted" in text
    assert "SelfDevelopmentProspectiveCollectorReceipt" in baseline
    assert "SelfDevelopmentL0StagingTransaction" in baseline

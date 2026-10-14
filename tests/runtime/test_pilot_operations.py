from runtime.pilot_operations import (
    build_pilot_review_queue,
    build_pilot_run_record,
    build_pilot_telemetry,
    review_pilot_run,
)
from runtime.pilot_profile import load_pilot_profile


def test_supervised_pilot_requires_digest_bound_human_review() -> None:
    profile = load_pilot_profile()
    readiness = {"roles": {role: {"mvp_ready": True} for role in profile["required_roles"]}}
    record = build_pilot_run_record(
        full_chain_report={"report_path": "full.json", "cases": [_case()]},
        transfer_report={
            "report_path": "transfer.json",
            "status": "eligible",
            "transfer_evidence": {"blind_projects": 2, "independent_lineages": 2, "handoff_loss": 0},
        },
        role_readiness=readiness,
        reviewer_adversarial={"status": "ok"},
    )

    assert record["status"] == "awaiting_human_review"
    assert record["human_review"]["status"] == "pending"
    reviewed = review_pilot_run(record, decision="approve", reviewer="architect")
    assert reviewed["status"] == "observed_approved"
    assert reviewed["human_review"]["evidence_digest"] == record["evidence_digest"]


def test_pilot_telemetry_stays_insufficient_before_observation_floor() -> None:
    profile = load_pilot_profile()
    readiness = {"roles": {role: {"mvp_ready": True} for role in profile["required_roles"]}}
    record = build_pilot_run_record(
        full_chain_report={"report_path": "full.json", "cases": [_case()]},
        transfer_report={
            "status": "eligible",
            "transfer_evidence": {"blind_projects": 2, "independent_lineages": 2, "handoff_loss": 0},
        },
        role_readiness=readiness,
        reviewer_adversarial={"status": "ok"},
    )
    reviewed = review_pilot_run(record, decision="approve", reviewer="architect")

    telemetry = build_pilot_telemetry([reviewed], profile=profile)

    assert telemetry["status"] == "insufficient_observations"
    assert telemetry["summary"]["approved_run_count"] == 1
    assert telemetry["summary"]["first_pass_rate"] == 1.0
    assert telemetry["summary"]["in_profile_first_pass_rate"] == 1.0
    assert telemetry["summary"]["admission_coverage_rate"] == 1.0


def test_pilot_telemetry_escalates_source_change_immediately() -> None:
    record = {
        "run_id": "unsafe",
        "status": "observed_stopped",
        "human_review": {"status": "completed"},
        "cases": [],
        "safety": {"source_code_changes": 1},
    }

    telemetry = build_pilot_telemetry([record])

    assert telemetry["status"] == "attention_required"
    assert telemetry["checks"]["source_changes_zero"] is False


def test_pending_review_requires_immediate_attention() -> None:
    telemetry = build_pilot_telemetry([{
        "run_id": "pending",
        "status": "awaiting_human_review",
        "human_review": {"status": "pending"},
        "cases": [_case()],
        "safety": {"source_code_changes": 0},
    }])

    assert telemetry["status"] == "attention_required"
    assert telemetry["summary"]["pending_review_count"] == 1


def test_reviewed_record_with_modified_evidence_requires_attention() -> None:
    profile = load_pilot_profile()
    readiness = {"roles": {role: {"mvp_ready": True} for role in profile["required_roles"]}}
    record = build_pilot_run_record(
        full_chain_report={"report_path": "full.json", "cases": [_case()]},
        transfer_report={
            "status": "eligible",
            "transfer_evidence": {"blind_projects": 2, "independent_lineages": 2, "handoff_loss": 0},
        },
        role_readiness=readiness,
        reviewer_adversarial={"status": "ok"},
    )
    reviewed = review_pilot_run(record, decision="approve", reviewer="architect")
    reviewed["cases"][0]["quality_score"] = 0.1

    telemetry = build_pilot_telemetry([reviewed], profile=profile)

    assert telemetry["status"] == "attention_required"
    assert telemetry["checks"]["review_digests_valid"] is False


def test_out_of_profile_chain_success_is_not_operational_first_pass() -> None:
    record = {
        "run_id": "outside",
        "execution_status": "controlled_stop",
        "status": "controlled_stop",
        "human_review": {"status": "pending"},
        "cases": [{
            **_case(),
            "first_pass": True,
            "admission": {"status": "blocked"},
        }],
        "safety": {"source_code_changes": 0},
    }

    telemetry = build_pilot_telemetry([record])

    assert telemetry["summary"]["first_pass_rate"] == 0.0
    assert telemetry["summary"]["admission_coverage_rate"] == 0.0
    assert telemetry["summary"]["controlled_stop_precision"] == 1.0
    assert telemetry["summary"]["controlled_stop_count"] == 1


def test_telemetry_separates_in_profile_quality_from_breadth():
    eligible = _review_record("ready", "awaiting_human_review", "eligible", [])
    eligible["cases"][0]["first_pass"] = True
    outside = _review_record("outside", "controlled_stop", "blocked", [])
    outside["cases"][0]["first_pass"] = False

    telemetry = build_pilot_telemetry([eligible, outside])

    assert telemetry["summary"]["first_pass_rate"] == 0.5
    assert telemetry["summary"]["in_profile_first_pass_rate"] == 1.0
    assert telemetry["summary"]["admission_coverage_rate"] == 0.5
    assert telemetry["summary"]["controlled_stop_precision"] == 1.0


def test_review_queue_separates_approval_rework_and_profile_stop() -> None:
    records = [
        _review_record("ready", "awaiting_human_review", "eligible", []),
        _review_record("weak", "controlled_stop", "eligible", ["executable_acceptance_callable"]),
        _review_record("outside", "controlled_stop", "blocked", []),
    ]

    queue = build_pilot_review_queue(records)

    assert [row["recommended_decision"] for row in queue["items"]] == ["approve", "rework", "stop"]
    assert queue["summary"] == {
        "decision_count": 3,
        "recommended_approve": 1,
        "recommended_rework": 1,
        "recommended_stop": 1,
    }


def _case() -> dict:
    return {
        "project": "one__parser",
        "status": "ok",
        "quality_score": 1.0,
        "failed_checks": [],
        "source_code_changes": False,
        "project_classification": {
            "project_stratum": "library_pure_transform",
            "risk_profiles": ["deterministic"],
        },
        "effect_mode": "pure",
    }


def _review_record(project: str, execution_status: str, admission: str, failed: list[str]) -> dict:
    return {
        "run_id": project,
        "report_path": f"{project}.json",
        "execution_status": execution_status,
        "evidence_digest": project * 4,
        "cases": [{
            **_case(),
            "project": project,
            "failed_checks": failed,
            "admission": {
                "status": admission,
                "blocking_reasons": ["project_stratum_allowed"] if admission == "blocked" else [],
            },
        }],
    }

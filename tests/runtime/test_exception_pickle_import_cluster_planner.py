import json
from pathlib import Path

from runtime.exception_pickle_import_cluster_planner import (
    run_exception_pickle_import_cluster_planner,
)


def test_import_cluster_planner_prioritizes_direct_file_batch_candidates(tmp_path: Path):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
                {
                    "project": "p2",
                    "target": "b.py:B.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "authlib",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": False,
                        "target_replay_risk": 8,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
                {
                    "project": "p3",
                    "target": "c.py:C.__init__",
                    "next_operator_lane": "self_assignment_extraction_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    assert result["status"] == "ready"
    assert result["cluster_count"] == 2
    assert result["recommended_next_cluster"]["cluster"] == "external_dependency:aiohttp"
    assert result["recommended_next_cluster"]["direct_file_batch_candidate_count"] == 1
    assert result["recommended_next_cluster"]["batch_readiness"] == "cluster_batch_ready"
    assert result["recommended_next_cluster"]["target_replay_risk_summary"] == {"low": 1}
    assert result["recommended_next_cluster"]["next_action"] == (
        "run_dependency_heavy_direct_file_batch"
    )


def test_import_cluster_planner_marks_partial_clusters_as_probe_required(tmp_path: Path):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
                {
                    "project": "p2",
                    "target": "b.py:B.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": False,
                        "target_replay_risk": 7,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    assert result["recommended_next_cluster"]["cluster"] == "external_dependency:aiohttp"
    assert result["recommended_next_cluster"]["direct_file_batch_candidate_count"] == 1
    assert result["recommended_next_cluster"]["batch_readiness"] == "partial_batch_probe_required"
    assert result["recommended_next_cluster"]["target_replay_risk_summary"] == {
        "high": 1,
        "low": 1,
    }
    assert result["recommended_next_cluster"]["next_action"] == (
        "probe_direct_file_subset_before_write"
    )


def test_import_cluster_planner_marks_project_local_subset_as_policy_probe(
    tmp_path: Path,
):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "app",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
                {
                    "project": "p2",
                    "target": "b.py:B.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "salt.utils",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "has_target_self_attribute_gap": True,
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    assert result["recommended_next_cluster"]["cluster"] == (
        "project_local_dependency:dependency_unavailable"
    )
    assert result["recommended_next_cluster"]["direct_file_batch_candidate_count"] == 1
    assert result["recommended_next_cluster"]["batch_readiness"] == (
        "partial_project_local_probe_required"
    )
    assert result["recommended_next_cluster"]["next_action"] == (
        "probe_project_local_direct_file_subset_before_write"
    )


def test_import_cluster_planner_ignores_incompatible_failed_probe_profile(
    tmp_path: Path,
):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "app",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    out_dir = tmp_path / "artifacts" / "project_development"
    out_dir.mkdir(parents=True)
    (out_dir / "exception_pickle_active_application_20260903T000000000000Z.json").write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationTrial",
            "generated_at": "2026-09-03T00:00:00+00:00",
            "update_application_ledger": False,
            "import_isolation_batch_profile": "dependency_heavy_direct_file",
            "import_isolation_cluster": "external_dependency:app",
            "attempts": [
                {
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                    "candidate": {
                        "project": "p1",
                        "target": "a.py:A.__init__",
                    },
                }
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    cluster = result["recommended_next_cluster"]
    assert cluster["cluster"] == "project_local_dependency:dependency_unavailable"
    assert cluster["failed_direct_file_probe_count"] == 0
    assert cluster["batch_readiness"] == "project_local_cluster_probe_required"
    assert cluster["next_action"] == "run_project_local_direct_file_probe"


def test_import_cluster_planner_counts_compatible_project_local_failed_probe(
    tmp_path: Path,
):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "app",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    out_dir = tmp_path / "artifacts" / "project_development"
    out_dir.mkdir(parents=True)
    probe = out_dir / "exception_pickle_active_application_20260903T000000000000Z.json"
    probe.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationTrial",
            "generated_at": "2026-09-03T00:00:00+00:00",
            "update_application_ledger": False,
            "import_isolation_batch_profile": "project_local_direct_file",
            "import_isolation_cluster": "project_local_dependency:dependency_unavailable",
            "attempts": [
                {
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                    "candidate": {
                        "project": "p1",
                        "target": "a.py:A.__init__",
                    },
                }
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    cluster = result["recommended_next_cluster"]
    assert cluster["failed_direct_file_probe_count"] == 1
    assert cluster["latest_failed_probe_reports"] == [probe.as_posix()]
    assert cluster["batch_readiness"] == "direct_file_probe_failed"
    assert cluster["next_action"] == "diagnose_failed_direct_file_probe"


def test_import_cluster_planner_uses_report_only_failed_probe_evidence(tmp_path: Path):
    report = tmp_path / "bi.json"
    report.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
                {
                    "project": "p2",
                    "target": "b.py:B.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "yarl",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "blocker_kind": "semantic_replay_dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    out_dir = tmp_path / "artifacts" / "project_development"
    out_dir.mkdir(parents=True)
    probe = out_dir / "exception_pickle_active_application_20260903T000000000000Z.json"
    probe.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationTrial",
            "generated_at": "2026-09-03T00:00:00+00:00",
            "import_isolation_batch_profile": "dependency_heavy_direct_file",
            "import_isolation_cluster": "external_dependency:aiohttp",
            "update_application_ledger": False,
            "attempts": [
                {
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_behavior_mismatch",
                    "candidate": {
                        "project": "p1",
                        "target": "a.py:A.__init__",
                    },
                }
            ],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_import_cluster_planner(
        root=tmp_path,
        blocker_intelligence_path=report,
    )

    clusters = {row["cluster"]: row for row in result["clusters"]}
    aiohttp = clusters["external_dependency:aiohttp"]
    assert aiohttp["batch_readiness"] == "direct_file_probe_failed"
    assert aiohttp["failed_direct_file_probe_count"] == 1
    assert aiohttp["failed_direct_file_probe_blocker_summary"] == {
        "semantic_replay_behavior_mismatch": 1,
    }
    assert aiohttp["latest_failed_probe_reports"] == [probe.as_posix()]
    assert aiohttp["next_action"] == "diagnose_failed_direct_file_probe"
    assert result["recommended_next_cluster"]["cluster"] == "external_dependency:yarl"

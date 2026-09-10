from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_can_select_dependency_heavy_direct_file_batch(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "batch-filter"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class RiskyExternalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class DirectExternalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "batch-filter",
                    "project_root": "batch-filter",
                    "path": "pkg.py",
                    "class_name": "RiskyExternalError",
                    "score": 100,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "batch-filter",
                    "project_root": "batch-filter",
                    "path": "pkg.py",
                    "class_name": "DirectExternalError",
                    "score": 1,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": [
                {
                    "project": "batch-filter",
                    "target": "pkg.py:RiskyExternalError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
                {
                    "project": "batch-filter",
                    "target": "pkg.py:DirectExternalError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
            ],
        }),
        encoding="utf-8",
    )
    report_dir = tmp_path / "artifacts" / "project_development"
    report_dir.mkdir(parents=True)
    (report_dir / "exception_pickle_blocker_intelligence_20260902T010101000000Z.json").write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "batch-filter",
                    "target": "pkg.py:RiskyExternalError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": False,
                        "target_replay_risk": 7,
                        "subtype": "dependency_unavailable",
                    },
                },
                {
                    "project": "batch-filter",
                    "target": "pkg.py:DirectExternalError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "yarl",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        only_import_isolation_frontier=True,
        import_isolation_batch_profile="dependency_heavy_direct_file",
    )

    assert report["import_isolation_batch_profile"] == "dependency_heavy_direct_file"
    assert report["import_isolation_batch_summary"]["case_count"] == 1
    assert report["selected_application"]["candidate"]["target"] == (
        "pkg.py:DirectExternalError.__init__"
    )


def test_active_application_batch_run_can_accept_multiple_candidates(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "multi-batch"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class FirstExternalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class SecondExternalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class ThirdExternalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    candidates = []
    cases = []
    blocked = []
    for score, name in [(30, "FirstExternalError"), (20, "SecondExternalError"), (10, "ThirdExternalError")]:
        target = f"pkg.py:{name}.__init__"
        candidates.append({
            "canonical_project": "multi-batch",
            "project_root": "multi-batch",
            "path": "pkg.py",
            "class_name": name,
            "score": score,
            "required_constructor_parameters": ["message"],
            "stored_constructor_parameters": ["message"],
        })
        blocked.append({
            "project": "multi-batch",
            "target": target,
            "status": "blocked_semantic_replay",
            "blocker_kind": "semantic_replay_dependency_unavailable",
        })
        cases.append({
            "project": "multi-batch",
            "target": target,
            "next_operator_lane": "import_dependency_isolation_candidate",
            "import_isolation_profile": {
                "missing_import": "aiohttp",
                "missing_import_kind": "external_dependency",
                "direct_file_preferred": True,
                "target_replay_risk": 0,
                "subtype": "dependency_unavailable",
            },
        })
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({"artifact_type": "ExceptionPickleCandidateAudit", "candidates": candidates}),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": blocked,
        }),
        encoding="utf-8",
    )
    report_dir = tmp_path / "artifacts" / "project_development"
    report_dir.mkdir(parents=True)
    (report_dir / "exception_pickle_blocker_intelligence_20260902T010101000000Z.json").write_text(
        json.dumps({"artifact_type": "ExceptionPickleBlockerIntelligence", "cases": cases}),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        only_import_isolation_frontier=True,
        import_isolation_batch_profile="dependency_heavy_direct_file",
        maximum_accepted_applications=2,
    )
    ledger_report = json.loads(application_ledger.read_text(encoding="utf-8"))

    assert report["status"] == "applied_active_kb"
    assert report["selected_application_count"] == 2
    assert report["stop_reason"] == "maximum_accepted_applications_reached"
    assert ledger_report["active_pattern_applied_count"] == 2
    assert [item["candidate"]["target"] for item in report["selected_applications"]] == [
        "pkg.py:FirstExternalError.__init__",
        "pkg.py:SecondExternalError.__init__",
    ]


def test_active_application_batch_profile_can_limit_to_cluster(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "cluster-batch"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class AuthError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class AioError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "cluster-batch",
                    "project_root": "cluster-batch",
                    "path": "pkg.py",
                    "class_name": "AuthError",
                    "score": 1,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "cluster-batch",
                    "project_root": "cluster-batch",
                    "path": "pkg.py",
                    "class_name": "AioError",
                    "score": 100,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": [
                {
                    "project": "cluster-batch",
                    "target": "pkg.py:AuthError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
                {
                    "project": "cluster-batch",
                    "target": "pkg.py:AioError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
            ],
        }),
        encoding="utf-8",
    )
    report_dir = tmp_path / "artifacts" / "project_development"
    report_dir.mkdir(parents=True)
    (report_dir / "exception_pickle_blocker_intelligence_20260902T010101000000Z.json").write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleBlockerIntelligence",
            "cases": [
                {
                    "project": "cluster-batch",
                    "target": "pkg.py:AuthError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "authlib",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                    },
                },
                {
                    "project": "cluster-batch",
                    "target": "pkg.py:AioError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        only_import_isolation_frontier=True,
        import_isolation_batch_profile="dependency_heavy_direct_file",
        import_isolation_cluster="external_dependency:authlib",
    )

    assert report["import_isolation_cluster"] == "external_dependency:authlib"
    assert report["import_isolation_batch_summary"]["case_count"] == 1
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:AuthError.__init__"



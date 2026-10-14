from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_project_local_profile_selects_safe_subset(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "project-local-batch"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class SafeLocalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class SelfGapLocalError(Exception):\n"
        "    def __init__(self, message):\n"
        "        super().__init__(message)\n\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "project-local-batch",
                    "project_root": "project-local-batch",
                    "path": "pkg.py",
                    "class_name": "SafeLocalError",
                    "score": 10,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "project-local-batch",
                    "project_root": "project-local-batch",
                    "path": "pkg.py",
                    "class_name": "SelfGapLocalError",
                    "score": 20,
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
                    "project": "project-local-batch",
                    "target": "pkg.py:SafeLocalError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
                {
                    "project": "project-local-batch",
                    "target": "pkg.py:SelfGapLocalError.__init__",
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
                    "project": "project-local-batch",
                    "target": "pkg.py:SafeLocalError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "app",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                    },
                },
                {
                    "project": "project-local-batch",
                    "target": "pkg.py:SelfGapLocalError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "app",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                        "subtype": "dependency_unavailable",
                        "has_target_self_attribute_gap": True,
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
        import_isolation_batch_profile="project_local_direct_file",
        import_isolation_cluster="project_local_dependency:dependency_unavailable",
    )

    assert report["import_isolation_batch_summary"]["case_count"] == 1
    assert report["import_isolation_batch_summary"]["selection_constraints"][
        "missing_import_kind"
    ] == "project_local_dependency"
    assert report["selected_application"]["candidate"]["target"] == (
        "pkg.py:SafeLocalError.__init__"
    )


def test_active_application_direct_file_stub_supports_path_join_side_effect(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "path-side-effect-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "from app.config import settings\n\n"
        "STORE_DIR = settings.data_dir / 'job_store'\n\n"
        "class JobCancelledError(Exception):\n"
        "    def __init__(self, job_id):\n"
        "        self.job_id = job_id\n"
        "        super().__init__(f'Job {job_id} was cancelled')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "path-side-effect-project",
                "project_root": "path-side-effect-project",
                "path": "pkg.py",
                "class_name": "JobCancelledError",
                "score": 7,
                "required_constructor_parameters": ["job_id"],
                "stored_constructor_parameters": ["job_id"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"


def test_active_application_samples_endpoint_string(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "endpoint-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class NotFoundError(Exception):\n"
        "    def __init__(self, endpoint):\n"
        "        self.endpoint = endpoint\n"
        "        super().__init__(f'Endpoint not found: {endpoint}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "endpoint-project",
                "project_root": "endpoint-project",
                "path": "pkg.py",
                "class_name": "NotFoundError",
                "score": 7,
                "required_constructor_parameters": ["endpoint"],
                "stored_constructor_parameters": ["endpoint"],
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger.json",
    )

    assert report["status"] == "applied_active_kb"


def test_active_application_does_not_readmit_behavior_mismatch_after_source_aware_sample(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "reader"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ReaderError(Exception):\n"
        "    def __init__(self, error_type, line):\n"
        "        self.error_type = error_type\n"
        "        self.line = line\n"
        "        super().__init__(f'{error_type}: {line[:100]}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "reader",
                "project_root": "reader",
                "path": "pkg.py",
                "class_name": "ReaderError",
                "score": 7,
                "required_constructor_parameters": ["error_type", "line"],
                "stored_constructor_parameters": ["error_type", "line"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": [{
                "project": "reader",
                "target": "pkg.py:ReaderError.__init__",
                "status": "blocked_semantic_replay",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        only_readmission_frontier=True,
    )

    assert report["status"] == "blocked"
    assert report["attempt_count"] == 0
    assert report["selected_application"] is None


def test_active_application_does_not_readmit_behavior_mismatch_after_known_object_sample_delta(
    tmp_path: Path,
):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "flags"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class TooManyFlags(Exception):\n"
        "    def __init__(self, flag, values):\n"
        "        self.flag = flag\n"
        "        self.values = values\n"
        "        super().__init__(f'expected {flag.max_args} got {len(values)}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "flags",
                "project_root": "flags",
                "path": "pkg.py",
                "class_name": "TooManyFlags",
                "score": 7,
                "required_constructor_parameters": ["flag", "values"],
                "stored_constructor_parameters": ["flag", "values"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [],
            "blocked_cases": [{
                "project": "flags",
                "target": "pkg.py:TooManyFlags.__init__",
                "status": "blocked_semantic_replay",
                "blocker_kind": "semantic_replay_behavior_mismatch",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        only_readmission_frontier=True,
    )

    assert report["status"] == "blocked"
    assert report["attempt_count"] == 0
    assert report["selected_application"] is None



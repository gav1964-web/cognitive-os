from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_does_not_readmit_target_after_fresh_replay_blocker(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "response-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ResponseError(Exception):\n"
        "    def __init__(self, response):\n"
        "        self.response = response\n"
        "        super().__init__(response)\n\n"
        "class CleanError(Exception):\n"
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
                    "canonical_project": "response-project",
                    "project_root": "response-project",
                    "path": "pkg.py",
                    "class_name": "ResponseError",
                    "score": 100,
                    "required_constructor_parameters": ["response"],
                    "stored_constructor_parameters": ["response"],
                },
                {
                    "canonical_project": "response-project",
                    "project_root": "response-project",
                    "path": "pkg.py",
                    "class_name": "CleanError",
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
                    "project": "response-project",
                    "target": "pkg.py:ResponseError.__init__",
                    "status": "blocked_precheck",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "response-project",
                    "target": "pkg.py:ResponseError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_import_failed",
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
    )

    assert report["status"] == "applied_active_kb"
    assert report["attempt_count"] == 1
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:CleanError.__init__"


def test_active_application_can_limit_selection_to_import_isolation_frontier(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "import-blocked"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ImportBlockedError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class CleanError(Exception):\n"
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
                    "canonical_project": "import-blocked",
                    "project_root": "import-blocked",
                    "path": "pkg.py",
                    "class_name": "ImportBlockedError",
                    "score": 10,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "import-blocked",
                    "project_root": "import-blocked",
                    "path": "pkg.py",
                    "class_name": "CleanError",
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
            "blocked_cases": [{
                "project": "import-blocked",
                "target": "pkg.py:ImportBlockedError.__init__",
                "status": "blocked_semantic_replay",
                "blocker_kind": "semantic_replay_dependency_unavailable",
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
        only_import_isolation_frontier=True,
    )

    assert report["only_import_isolation_frontier"] is True
    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == (
        "pkg.py:ImportBlockedError.__init__"
    )


def test_active_application_can_limit_import_isolation_by_missing_import_kind(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "kind-filter"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class StdlibCompatError(Exception):\n"
        "    def __init__(self, message):\n"
        "        self.message = message\n"
        "        super().__init__(message)\n\n"
        "class ExternalDepError(Exception):\n"
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
                    "canonical_project": "kind-filter",
                    "project_root": "kind-filter",
                    "path": "pkg.py",
                    "class_name": "ExternalDepError",
                    "score": 100,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "kind-filter",
                    "project_root": "kind-filter",
                    "path": "pkg.py",
                    "class_name": "StdlibCompatError",
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
                    "project": "kind-filter",
                    "target": "pkg.py:ExternalDepError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_dependency_unavailable",
                },
                {
                    "project": "kind-filter",
                    "target": "pkg.py:StdlibCompatError.__init__",
                    "status": "blocked_semantic_replay",
                    "blocker_kind": "semantic_replay_import_failed",
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
                    "project": "kind-filter",
                    "target": "pkg.py:ExternalDepError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "aiohttp",
                        "missing_import_kind": "external_dependency",
                    },
                },
                {
                    "project": "kind-filter",
                    "target": "pkg.py:StdlibCompatError.__init__",
                    "next_operator_lane": "import_dependency_isolation_candidate",
                    "import_isolation_profile": {
                        "missing_import": "types:GenericAlias",
                        "missing_import_kind": "stdlib_symbol_compat",
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
        import_isolation_missing_kind="stdlib_symbol_compat",
    )

    assert report["status"] == "applied_active_kb"
    assert report["import_isolation_missing_kind"] == "stdlib_symbol_compat"
    assert report["selected_application"]["candidate"]["target"] == (
        "pkg.py:StdlibCompatError.__init__"
    )



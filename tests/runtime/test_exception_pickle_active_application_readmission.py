from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_can_limit_selection_to_readmission_frontier(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "response-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ResponseError(Exception):\n"
        "    def __init__(self, response):\n"
        "        self.response = response\n"
        "        super().__init__(response)\n\n"
        "class NewError(Exception):\n"
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
                    "class_name": "NewError",
                    "score": 100,
                    "required_constructor_parameters": ["message"],
                    "stored_constructor_parameters": ["message"],
                },
                {
                    "canonical_project": "response-project",
                    "project_root": "response-project",
                    "path": "pkg.py",
                    "class_name": "ResponseError",
                    "score": 1,
                    "required_constructor_parameters": ["response"],
                    "stored_constructor_parameters": ["response"],
                },
            ],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [{
                "project": "response-project",
                "target": "pkg.py:NewError.__init__",
                "status": "applied_active_kb",
            }],
            "blocked_cases": [{
                "project": "response-project",
                "target": "pkg.py:ResponseError.__init__",
                "status": "blocked_precheck",
                "blocker_kind": "semantic_sample_shape_unsupported",
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

    assert report["status"] == "applied_active_kb"
    assert report["only_readmission_frontier"] is True
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:ResponseError.__init__"


def test_active_application_can_filter_readmission_by_subtype(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "subtype-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class DirectError(Exception):\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "        super().__init__(value)\n\n"
        "class DerivedError(Exception):\n"
        "    def __init__(self, message, context):\n"
        "        self.message = message\n"
        "        self.context = context\n"
        "        super().__init__(f'{message}: {context}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "subtype-project",
                    "project_root": "subtype-project",
                    "path": "pkg.py",
                    "class_name": "DirectError",
                    "score": 100,
                    "required_constructor_parameters": ["value"],
                    "stored_constructor_parameters": ["value"],
                },
                {
                    "canonical_project": "subtype-project",
                    "project_root": "subtype-project",
                    "path": "pkg.py",
                    "class_name": "DerivedError",
                    "score": 1,
                    "required_constructor_parameters": ["message", "context"],
                    "stored_constructor_parameters": ["message", "context"],
                    "formatted_super_argument": True,
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
                    "project": "subtype-project",
                    "target": "pkg.py:DirectError.__init__",
                    "status": "blocked_precheck",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "subtype-project",
                    "target": "pkg.py:DerivedError.__init__",
                    "status": "blocked_precheck",
                    "blocker_kind": "semantic_sample_shape_unsupported",
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
        only_readmission_frontier=True,
        readmission_subtype="derived_message_sample",
    )

    assert report["status"] == "applied_active_kb"
    assert report["readmission_subtype"] == "derived_message_sample"
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:DerivedError.__init__"


def test_active_application_readmits_static_patch_shape_after_patcher_delta(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "shape-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class MessageOnlyError(Exception):\n"
        "    def __init__(self, message):\n"
        "        super().__init__()\n"
        "        self.message = message\n"
        "\n"
        "    def __str__(self):\n"
        "        return str(self.message)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "shape-project",
                "project_root": "shape-project",
                "path": "pkg.py",
                "class_name": "MessageOnlyError",
                "score": 1,
                "required_constructor_parameters": ["message"],
                "stored_constructor_parameters": ["message"],
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
                "project": "shape-project",
                "target": "pkg.py:MessageOnlyError.__init__",
                "status": "blocked_static_patch",
                "blocker_kind": "static_patch_shape_unsupported",
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

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:MessageOnlyError.__init__"


def test_active_application_does_not_repeat_already_applied_readmission_target(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "response-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class ResponseError(Exception):\n"
        "    def __init__(self, response):\n"
        "        self.response = response\n"
        "        super().__init__(response)\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "response-project",
                "project_root": "response-project",
                "path": "pkg.py",
                "class_name": "ResponseError",
                "score": 1,
                "required_constructor_parameters": ["response"],
                "stored_constructor_parameters": ["response"],
            }],
        }),
        encoding="utf-8",
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [{
                "project": "response-project",
                "target": "pkg.py:ResponseError.__init__",
                "status": "applied_active_kb",
            }],
            "blocked_cases": [{
                "project": "response-project",
                "target": "pkg.py:ResponseError.__init__",
                "status": "blocked_precheck",
                "blocker_kind": "semantic_sample_shape_unsupported",
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



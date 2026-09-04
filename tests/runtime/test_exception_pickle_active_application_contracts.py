from __future__ import annotations

from tests.runtime.exception_pickle_active_application_helpers import *

def test_active_application_consumes_admitted_object_contract(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "domain-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class DomainError(Exception):\n"
        "    def __init__(self, tenant_domain):\n"
        "        self.tenant_domain = tenant_domain\n"
        "        super().__init__(f'domain={tenant_domain}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "domain-project",
                "project_root": "domain-project",
                "path": "pkg.py",
                "class_name": "DomainError",
                "score": 7,
                "required_constructor_parameters": ["tenant_domain"],
                "stored_constructor_parameters": ["tenant_domain"],
            }],
        }),
        encoding="utf-8",
    )
    admission = tmp_path / "admission.json"
    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "source_apply": False,
            "kb_promotion": False,
            "admitted_contracts": {
                "domain-project::pkg.py:DomainError.__init__": {
                    "project": "domain-project",
                    "target": "pkg.py:DomainError.__init__",
                    "contracts": [{
                        "parameter": "tenant_domain",
                        "contract_kind": "string_like",
                        "confidence": 0.72,
                        "source_backed": True,
                        "promotion_allowed": False,
                    }],
                }
            },
        }),
        encoding="utf-8",
    )

    blocked = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution-blocked",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger-blocked.json",
    )
    applied = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution-applied",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=tmp_path / "application-ledger-applied.json",
        object_contract_admission_path=admission,
    )

    assert blocked["status"] == "blocked"
    assert blocked["attempts"][0]["blocker_kind"] == "semantic_sample_shape_unsupported"
    assert applied["status"] == "applied_active_kb"
    assert applied["selected_application"]["object_contracts"]["tenant_domain"]["contract_kind"] == "string_like"


def test_active_application_retries_previous_sample_block_when_contract_admitted(tmp_path: Path):
    _write_active_catalog(tmp_path)
    ledger = _write_transfer_ledger(tmp_path)
    project = tmp_path / "domain-project"
    project.mkdir()
    (project / "pkg.py").write_text(
        "class DomainError(Exception):\n"
        "    def __init__(self, domain):\n"
        "        self.domain = domain\n"
        "        super().__init__(f'domain={domain}')\n",
        encoding="utf-8",
    )
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "domain-project",
                "project_root": "domain-project",
                "path": "pkg.py",
                "class_name": "DomainError",
                "score": 7,
                "required_constructor_parameters": ["domain"],
                "stored_constructor_parameters": ["domain"],
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
                "project": "domain-project",
                "target": "pkg.py:DomainError.__init__",
                "status": "blocked_precheck",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )
    admission = tmp_path / "admission.json"
    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "source_apply": False,
            "kb_promotion": False,
            "admitted_contracts": {
                "domain-project::pkg.py:DomainError.__init__": {
                    "project": "domain-project",
                    "target": "pkg.py:DomainError.__init__",
                    "contracts": [{
                        "parameter": "domain",
                        "contract_kind": "string_like",
                        "confidence": 0.72,
                        "source_backed": True,
                        "promotion_allowed": False,
                    }],
                }
            },
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_active_application_trial(
        root=tmp_path,
        execution_dir=tmp_path / "execution",
        audit_path=audit,
        transfer_ledger_path=ledger,
        application_ledger_path=application_ledger,
        object_contract_admission_path=admission,
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:DomainError.__init__"


def test_active_application_retries_previous_sample_block_when_materializer_now_supports_it(tmp_path: Path):
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
                "score": 7,
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
            "cases": [],
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
    )

    assert report["status"] == "applied_active_kb"
    assert report["selected_application"]["candidate"]["target"] == "pkg.py:ResponseError.__init__"



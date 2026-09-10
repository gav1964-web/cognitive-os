import json
from pathlib import Path

from runtime.exception_pickle_object_contract_admission import (
    load_admitted_object_contracts,
    run_exception_pickle_object_contract_admission,
)


def test_object_contract_admission_allows_only_safe_source_backed_contracts(tmp_path: Path):
    audit = tmp_path / "object_audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAudit",
            "cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:AttrError.__init__",
                    "contracts": [{
                        "parameter": "tarinfo",
                        "contract_kind": "attribute_object",
                        "confidence": 0.8,
                        "source_backed": True,
                        "promotion_allowed": False,
                    }],
                },
                {
                    "project": "pkg",
                    "target": "errors.py:MapError.__init__",
                    "contracts": [{
                        "parameter": "body",
                        "contract_kind": "mapping_object",
                        "confidence": 0.82,
                        "source_backed": True,
                        "promotion_allowed": False,
                    }],
                },
                {
                    "project": "pkg",
                    "target": "errors.py:WeakError.__init__",
                    "contracts": [{
                        "parameter": "domain",
                        "contract_kind": "string_like",
                        "confidence": 0.69,
                        "source_backed": True,
                        "promotion_allowed": False,
                    }],
                },
            ],
            "source_apply": False,
            "kb_promotion": False,
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_admission(
        root=tmp_path,
        object_contract_audit_path=audit,
    )

    assert report["status"] == "ready"
    assert report["admitted_case_count"] == 1
    assert report["held_case_count"] == 2
    assert report["held_contract_summary"] == {"mapping_object": 1, "string_like": 1}
    assert "pkg::errors.py:AttrError.__init__" in report["admitted_contracts"]
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def test_load_admitted_object_contracts_requires_non_authoritative_artifact(tmp_path: Path):
    admission = tmp_path / "admission.json"
    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "source_apply": False,
            "kb_promotion": False,
            "admitted_contracts": {
                "pkg::errors.py:AttrError.__init__": {
                    "project": "pkg",
                    "target": "errors.py:AttrError.__init__",
                    "contracts": [],
                }
            },
        }),
        encoding="utf-8",
    )
    assert load_admitted_object_contracts(tmp_path, admission)

    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "source_apply": True,
            "kb_promotion": False,
            "admitted_contracts": {},
        }),
        encoding="utf-8",
    )
    assert load_admitted_object_contracts(tmp_path, admission) == {}


def test_object_contract_admission_allows_bounded_literal_mapping_contract(tmp_path: Path):
    audit = tmp_path / "object_audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAudit",
            "cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:BodyError.__init__",
                    "contracts": [{
                        "parameter": "body",
                        "contract_kind": "mapping_object",
                        "confidence": 0.82,
                        "source_backed": True,
                        "promotion_allowed": False,
                        "evidence": {
                            "mapping_keys": ["message", "status"],
                            "method_calls": [],
                        },
                    }],
                },
                {
                    "project": "pkg",
                    "target": "errors.py:UnsafeBodyError.__init__",
                    "contracts": [{
                        "parameter": "body",
                        "contract_kind": "mapping_object",
                        "confidence": 0.82,
                        "source_backed": True,
                        "promotion_allowed": False,
                        "evidence": {
                            "mapping_keys": ["message"],
                            "method_calls": ["items"],
                        },
                    }],
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_admission(
        root=tmp_path,
        object_contract_audit_path=audit,
    )

    assert report["admitted_case_count"] == 1
    assert report["held_case_count"] == 1
    assert report["admitted_contract_summary"] == {"mapping_object": 1}
    assert report["held_contract_summary"] == {"mapping_object": 1}
    assert "pkg::errors.py:BodyError.__init__" in report["admitted_contracts"]


def test_object_contract_admission_allows_only_bounded_zero_arg_method_contracts(tmp_path: Path):
    audit = tmp_path / "object_audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAudit",
            "cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:JsonError.__init__",
                    "contracts": [{
                        "parameter": "response",
                        "contract_kind": "method_object",
                        "confidence": 0.76,
                        "source_backed": True,
                        "promotion_allowed": False,
                        "evidence": {
                            "method_calls": ["json"],
                            "method_call_arg_counts": {"json": 0},
                            "method_return_profiles": {"json": "mapping"},
                        },
                    }],
                },
                {
                    "project": "pkg",
                    "target": "errors.py:UnsafeJsonError.__init__",
                    "contracts": [{
                        "parameter": "response",
                        "contract_kind": "method_object",
                        "confidence": 0.76,
                        "source_backed": True,
                        "promotion_allowed": False,
                        "evidence": {
                            "method_calls": ["json"],
                            "method_call_arg_counts": {"json": 1},
                            "method_return_profiles": {"json": "mapping"},
                        },
                    }],
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_object_contract_admission(
        root=tmp_path,
        object_contract_audit_path=audit,
    )

    assert report["admitted_case_count"] == 1
    assert report["held_case_count"] == 1
    assert report["admitted_contract_summary"] == {"method_object": 1}
    assert report["held_contract_summary"] == {"method_object": 1}
    assert "pkg::errors.py:JsonError.__init__" in report["admitted_contracts"]

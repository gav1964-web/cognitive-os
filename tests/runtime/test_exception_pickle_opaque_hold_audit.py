import json
from pathlib import Path

from runtime.exception_pickle_opaque_hold_audit import run_exception_pickle_opaque_hold_audit


def test_opaque_hold_audit_summarizes_held_contract_reasons(tmp_path: Path):
    admission = tmp_path / "admission.json"
    admission.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleObjectContractAdmission",
            "cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:OpaqueError.__init__",
                    "status": "held",
                    "contracts": [{
                        "parameter": "request",
                        "contract_kind": "opaque_hold",
                        "evidence": {
                            "opaque_reasons": ["parameter_method_call"],
                            "method_calls": ["json"],
                            "line_numbers": [10],
                        },
                    }],
                },
                {
                    "project": "pkg",
                    "target": "errors.py:ReadyError.__init__",
                    "status": "admitted_for_replay",
                    "contracts": [{
                        "parameter": "value",
                        "contract_kind": "string_like",
                    }],
                },
            ],
            "source_apply": False,
            "kb_promotion": False,
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_opaque_hold_audit(
        root=tmp_path,
        object_contract_admission_path=admission,
    )

    assert report["status"] == "ready"
    assert report["case_count"] == 1
    assert report["opaque_parameter_count"] == 1
    assert report["reason_summary"] == {"parameter_method_call": 1}
    assert report["parameter_summary"]["request"]["count"] == 1
    assert report["cases"][0]["opaque_contracts"][0]["triage"] == "inspect_method_contract"
    assert report["llm_authority"] == "advisory_only"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False

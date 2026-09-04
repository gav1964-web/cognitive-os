import json
from pathlib import Path

from runtime.exception_pickle_autonomous_shadow import _sample_constructor_value
from runtime.exception_pickle_materializer_audit import run_exception_pickle_materializer_audit


def test_materializer_audit_groups_unsupported_shapes(tmp_path: Path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "ParserError",
                    "required_constructor_parameters": ["message", "node_id", "container"],
                    "stored_constructor_parameters": ["message", "node_id", "container"],
                },
                {
                    "canonical_project": "pkg",
                    "project_root": "pkg",
                    "path": "errors.py",
                    "class_name": "RangeError",
                    "required_constructor_parameters": ["minimum", "maximum"],
                    "stored_constructor_parameters": ["minimum", "maximum"],
                },
            ],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "blocked_cases": [
                {
                    "project": "pkg",
                    "target": "errors.py:ParserError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
                {
                    "project": "pkg",
                    "target": "errors.py:RangeError.__init__",
                    "blocker_kind": "semantic_sample_shape_unsupported",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_materializer_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["status"] == "ready"
    assert report["unsupported_case_count"] == 1
    assert report["unsupported_parameter_count"] == 1
    assert report["recommendation_summary"] == {"candidate_primitive_string": 1}
    assert report["recommendations"][0]["parameter"] == "node_id"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def test_materializer_audit_recommends_safe_primitive_frontier(tmp_path: Path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "CooldownError",
                "required_constructor_parameters": [
                    "retry_after",
                    "status",
                    "ad_title",
                    "type_",
                    "request",
                ],
                "stored_constructor_parameters": [
                    "retry_after",
                    "status",
                    "ad_title",
                    "type_",
                    "request",
                ],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:CooldownError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_materializer_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    by_name = {row["parameter"]: row["recommendation"] for row in report["recommendations"]}
    assert by_name == {"request": "object_like_hold"}


def test_materializer_audit_excludes_later_applied_targets(tmp_path: Path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": [{
                "canonical_project": "pkg",
                "project_root": "pkg",
                "path": "errors.py",
                "class_name": "BodyError",
                "required_constructor_parameters": ["body"],
                "stored_constructor_parameters": ["body"],
            }],
        }),
        encoding="utf-8",
    )
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationLedger",
            "cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "status": "applied_active_kb",
            }],
            "blocked_cases": [{
                "project": "pkg",
                "target": "errors.py:BodyError.__init__",
                "blocker_kind": "semantic_sample_shape_unsupported",
            }],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_materializer_audit(
        root=tmp_path,
        audit_path=audit,
        application_ledger_path=ledger,
    )

    assert report["unsupported_case_count"] == 0
    assert report["recommendation_summary"] == {}


def test_materializer_supports_source_backed_exception_frontier_names() -> None:
    assert _sample_constructor_value("error_message") == "sample-error_message"
    assert _sample_constructor_value("rev") == "sample-rev"
    assert _sample_constructor_value("output") == "sample-output"
    assert _sample_constructor_value("parents") == ["sample-parents"]
    assert _sample_constructor_value("ref_infos") == ["sample-ref_infos"]
    assert _sample_constructor_value("record") == {"id": "sample-record"}
    assert _sample_constructor_value("instance")["__sample__"] == "named_object"
    assert _sample_constructor_value("driver_error") == {
        "__sample__": "exception",
        "message": "sample-driver_error",
    }
    assert _sample_constructor_value("content") == {"__sample__": "bytes", "value": "sample-content"}
    assert _sample_constructor_value("auth_message") == "sample-auth-message"
    assert _sample_constructor_value("spec") == {"__sample__": "format_object", "value": "sample-spec"}
    assert _sample_constructor_value("dependents") == [
        {"__sample__": "format_object", "value": "sample-dependent"}
    ]
    assert _sample_constructor_value("exceptions") == {
        "sample-objective": [
            {"__sample__": "exception", "message": "sample-exception"},
            ["sample-traceback"],
        ]
    }
    assert _sample_constructor_value("scored_successfully") == {"sample-objective": 1.0}

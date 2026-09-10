import json
from pathlib import Path

from runtime.exception_pickle_derived_message_audit import (
    run_exception_pickle_derived_message_audit,
)


def test_derived_message_audit_splits_operational_lanes(tmp_path: Path):
    intelligence = tmp_path / "intelligence.json"
    intelligence.write_text(
        json.dumps({
            "cases": [
                _case("ready", patchable=True, dependency_light=True, ready_now=True),
                _case("import-heavy", patchable=True, dependency_light=False, ready_now=False),
                _case("patch-shape", patchable=False, dependency_light=True, ready_now=False),
                _case("plain", patchable=True, dependency_light=True, ready_now=False),
                {
                    "project": "other",
                    "target": "pkg.py:Other.__init__",
                    "readmission_profile": {"subtype": "source_backed_object_sample"},
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_derived_message_audit(
        root=tmp_path,
        blocker_intelligence_path=intelligence,
    )

    assert report["status"] == "ready"
    assert report["case_count"] == 4
    assert report["lane_summary"] == {
        "derived_message_import_isolation_first": 1,
        "derived_message_patch_shape_first": 1,
        "derived_message_ready_replay": 1,
        "derived_message_semantic_contrast": 1,
    }
    assert report["recommended_next_lane"]["lane"] == "derived_message_ready_replay"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def _case(
    project: str,
    *,
    patchable: bool,
    dependency_light: bool,
    ready_now: bool,
) -> dict:
    return {
        "project": project,
        "target": "pkg.py:DerivedError.__init__",
        "required_constructor_inputs": ["message", "context"],
        "source_facts": {"fact_tags": ["base_exception_argument_transform"]},
        "readmission_profile": {
            "subtype": "derived_message_sample",
            "required_input_signature": "message,context",
            "patchable": patchable,
            "dependency_light": dependency_light,
            "ready_now": ready_now,
            "replay_risk": 0 if dependency_light else 12,
            "static_patch_risk": 0 if patchable else 300,
        },
    }

import json
from pathlib import Path

from runtime.exception_pickle_class_state_contract_audit import (
    run_exception_pickle_class_state_contract_audit,
)


def test_class_state_contract_audit_groups_attribute_base_lanes(tmp_path: Path):
    report_path = tmp_path / "bi.json"
    report_path.write_text(
        json.dumps({
            "cases": [
                {
                    "project": "p1",
                    "target": "a.py:A.__init__",
                    "import_isolation_profile": {
                        "subtype": "attribute_base_metaclass_risk",
                        "missing_import": "dep",
                        "missing_import_kind": "external_dependency",
                        "direct_file_preferred": True,
                        "target_replay_risk": 0,
                    },
                    "required_constructor_inputs": ["message"],
                    "stored_constructor_inputs": ["message"],
                    "static_patch_readmission_supported": True,
                    "source_facts": {
                        "fact_tags": [
                            "attribute_base_class_definition",
                            "base_exception_argument_transform",
                        ],
                        "missing_self_attribute_reads": [],
                    },
                },
                {
                    "project": "p2",
                    "target": "b.py:B.__init__",
                    "import_isolation_profile": {
                        "subtype": "attribute_base_metaclass_risk",
                        "missing_import": "local",
                        "missing_import_kind": "project_local_dependency",
                        "direct_file_preferred": False,
                        "target_replay_risk": 4,
                        "has_target_self_attribute_gap": True,
                    },
                    "source_facts": {
                        "fact_tags": ["attribute_base_class_definition"],
                        "missing_self_attribute_reads": ["message"],
                    },
                },
                {
                    "project": "skip",
                    "target": "c.py:C.__init__",
                    "import_isolation_profile": {"subtype": "dependency_unavailable"},
                },
            ],
        }),
        encoding="utf-8",
    )

    report = run_exception_pickle_class_state_contract_audit(
        root=tmp_path,
        blocker_intelligence_path=report_path,
    )

    assert report["status"] == "ready"
    assert report["case_count"] == 2
    assert report["research_lane_summary"] == {
        "base_constructor_passthrough_contract": 1,
        "target_self_state_gap_research": 1,
    }
    assert report["recommended_next_lane"]["research_lane"] == "base_constructor_passthrough_contract"
    assert report["cases"][0]["next_action"] == "derive parent constructor argument/state preservation rule before replay"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False

from __future__ import annotations

import json

from runtime.role_artifact_builder import load_artifact_builders
from runtime.role_artifact_interpreter import load_role_artifact_pipeline
from runtime.role_directory import load_role_directory
from runtime.role_definitions import load_role_definitions, role_definition_map, role_ids
from runtime.role_definitions import load_role_record_defaults
from runtime.role_operational_policy import role_operational_policy_report


def test_role_definitions_are_loaded_from_external_json():
    roles = load_role_definitions()
    directory = load_role_directory()

    assert roles
    assert role_ids() == tuple(role.role_id for role in roles)
    assert "architect" in role_definition_map()
    assert directory["policy"]["roles_are_source_of_truth"] is True
    assert directory["policy"]["runtime_is_interpreter"] is True
    assert directory["policy"]["role_specific_python_facades"] is False
    assert all(directory["roles"][role.role_id]["capabilities"] for role in roles)
    assert all(role.questions for role in roles)
    assert directory["schema_version"] == "role_directory.v2"
    assert all("contract" in directory["roles"][role.role_id] for role in roles)


def test_role_operational_policy_is_complete():
    report = role_operational_policy_report()

    assert report["artifact_type"] == "RoleOperationalPolicyReport"
    assert report["schema_version"] == "role_directory.v2"
    assert report["status"] == "ok"
    assert report["role_count"] >= 7
    assert report["summary"]["auto_promote_forbidden"] is True
    assert report["summary"]["kb_candidates_enabled"] == report["role_count"]


def test_new_role_can_be_added_without_code_change(tmp_path):
    role_path = tmp_path / "sql_architect.json"
    role_path.write_text(
        json.dumps(
            {
                "schema_version": "role_definition.v1",
                "role_id": "sql_architect",
                "label": "SQL Architect",
                "order": 10,
                "consumes": ["DatabaseSchema"],
                "produces": ["ArchitectureDecisionRecord"],
                "kb_filters": {"role_scope": ["sql_architect"]},
                "policy": {"source_mutation": "forbidden"},
                "questions": [
                    {
                        "id": "schema_boundary",
                        "question": "Где границы схемы?",
                        "answer": {"provider": "constant", "value": "derive from schema evidence"},
                        "evidence": ["schema"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    roles = load_role_definitions(str(tmp_path))

    assert [role.role_id for role in roles] == ["sql_architect"]
    assert roles[0].questions[0]["answer"]["provider"] == "constant"


def test_role_pipeline_and_builders_reference_external_role_definitions():
    known_roles = set(role_ids())
    builders = load_artifact_builders()
    pipeline = load_role_artifact_pipeline()
    defaults = load_role_record_defaults()

    assert known_roles
    assert all(config["role_id"] in known_roles for config in builders.values())
    for step in pipeline["steps"]:
        role_id = step["role_id"]
        builder_id = builders[next(key for key, value in builders.items() if value["role_id"] == role_id)]["builder_id"]

        assert role_id in known_roles
        assert builder_id in builders
        assert builders[builder_id]["role_id"] == role_id
    assert all(role in known_roles for roles in defaults.values() for role in roles)

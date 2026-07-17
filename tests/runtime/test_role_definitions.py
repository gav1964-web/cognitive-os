from __future__ import annotations

import json

from runtime.role_definitions import load_role_definitions, role_definition_map, role_ids


def test_role_definitions_are_loaded_from_external_json():
    roles = load_role_definitions()

    assert roles
    assert role_ids() == tuple(role.role_id for role in roles)
    assert "architect" in role_definition_map()
    assert all(role.questions for role in roles)


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

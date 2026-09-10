from __future__ import annotations

import json
from pathlib import Path

from runtime.project_architecture_knowledge import load_role_qa_records
from runtime.role_knowledge import role_knowledge_distribution
from runtime.synthetic_role_kb import write_synthetic_role_qa


def test_role_qa_records_are_loaded_as_kb_records(tmp_path: Path):
    path = tmp_path / "synthetic_role_qa.json"
    write_synthetic_role_qa(output=path, records_per_role=2)

    records = load_role_qa_records(str(path))
    distribution = role_knowledge_distribution(records)

    assert len(records) > 14
    assert records[0]["record_type"] == "role_qa"
    assert records[0]["evidence_strength"] == "synthetic"
    assert any(record.get("source_template") == "provider_interface_mapping" for record in records)
    roles = {row["role"]: row for row in distribution["roles"]}
    assert roles["architect"]["record_types"]["role_qa"] > 2
    assert roles["project_analyzer"]["record_types"]["role_qa"] > 2
    assert roles["architect"]["record_ids"][0].startswith("sqa_")

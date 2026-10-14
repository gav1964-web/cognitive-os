"""Load confirmed candidate-selection contrasts from the knowledge queue."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.knowledge_admission import load_kb_candidates


RECORD_TYPE = "foundation_selection_contrast"


def contrast_groups(root: Path) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for candidate in load_kb_candidates(root=root):
        record = dict(candidate.get("proposed_record") or {})
        if candidate.get("record_type") != RECORD_TYPE or not record.get("contrast_id"):
            continue
        group = groups.setdefault(str(record["contrast_id"]), {
            "id": str(record["contrast_id"]), "records": [], "projects": set(),
        })
        confirmed_projects = {
            str(row["project"])
            for value in candidate.get("source_cases") or []
            if (row := dict(value or {})).get("project")
            and row.get("status") in {"confirmed", "accepted", "verified"}
        }
        record["_confirmed_projects"] = sorted(confirmed_projects)
        group["records"].append(record)
        group["projects"].update(confirmed_projects)
    return sorted(groups.values(), key=lambda row: (-len(row["projects"]), row["id"]))

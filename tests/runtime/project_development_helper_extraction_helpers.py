from __future__ import annotations

from pathlib import Path

from runtime.programmer_patch_synthesizer import synthesize_patch_package
from runtime.project_development import load_project_development_policy
from runtime.project_development_delta import development_delta_transform


def _plan(operator_id: str, *, target: str = "writer.py:write_json", allowed: list[str] | None = None) -> dict:
    intent = {"operator_id": operator_id}
    if allowed is not None:
        intent["allowed_operator_ids"] = allowed
    return {
        "implementation_target": {"candidate": target},
        "expected_files": ["writer.py"],
        "implementation_delta": {
            "status": "ready",
            "intent": intent,
        },
    }


def _mapping_source(field_count: int) -> str:
    fields = ", ".join(f"'field_{index:02d}': row.strip()" for index in range(1, field_count + 1))
    return (
        "def normalize_rows(rows: list[str]) -> list[dict[str, str]]:\n"
        "    normalized = []\n"
        "    for row in rows:\n"
        "        normalized.append({" + fields + "})\n"
        "    return normalized\n"
    )







































__all__ = [name for name in globals() if not name.startswith("__")]

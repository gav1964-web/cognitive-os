"""Load the portable successful side of a staged selection contrast."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def recovery_contract(report: dict[str, Any]) -> dict[str, Any]:
    path = report.get("knowledge_candidate_path")
    if not path:
        return {}
    try:
        candidate = json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if candidate.get("record_type") != "foundation_selection_contrast":
        return {}
    successful = dict(dict(candidate.get("proposed_record") or {}).get("successful_contract") or {})
    if not successful:
        return {}
    minimum_returns = 1 if int(successful.get("return_paths") or 0) > 0 else 0
    output_basis = str(successful.get("output_inference_basis") or "")
    value_return = minimum_returns and output_basis in {
        "return_expression", "explicit_return_annotation",
    }
    contract = {
        "output_inference_basis": (
            "" if minimum_returns else str(successful.get("output_inference_basis") or "")
        ),
        "min_return_paths": minimum_returns,
        "forbidden_output_inference_basis": (
            ["explicit_none_annotation", "insufficient_structural_evidence", "no_value_return"]
            if value_return else []
        ),
        "no_observed_side_effects": not bool(successful.get("observed_side_effects")),
        "state_mutation": bool(successful.get("state_mutation")),
    }
    return {key: value for key, value in contract.items() if value not in ("", None, [])}

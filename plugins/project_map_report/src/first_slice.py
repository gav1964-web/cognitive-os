"""First-slice candidate anchors for project map reports."""

from __future__ import annotations

from typing import Any

from .core_paths import is_core_path
from .runtime_readiness_helpers import all_functions, is_safe_extraction_candidate


PREFERRED_FIRST_SLICE_PRIORITY = {
    "parse_bbox": 0,
    "point_in_bbox": 1,
    "set_incident_data": 2,
    "branches_atms": 3,
    "batch_key": 4,
    "create_mbtiles": 5,
    "download_file": 7,
    "is_codegen_supported_family": 6,
    "materialize_result": 7,
    "call_local_llm_text": 8,
    "call_local_llm": 9,
    "curl_fallback_http_body": 10,
    "parse_llm_http_body": 11,
    "parse_llm_text": 12,
    "normalize_llm_payload": 13,
    "extract_llm_payload": 14,
    "fetch_available_models": 15,
    "describe_module": 16,
    "build": 17,
    "build_key": 0,
    "get_request_id": 1,
    "add_request_id_middleware": 2,
    "provider_error_handler": 3,
    "assess_complexity": 4,
    "provider_error_to_http_exception": 5,
    "choose_model_from_complexity": 6,
    "_handle_chat_request": 7,
    "flush": 8,
    "chat_completions": 9,
}


def preferred_first_slice_candidates(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in all_functions(python_structure):
        if not is_core_path(str(item.get("path", ""))):
            continue
        name = str(item.get("name") or "")
        if name not in PREFERRED_FIRST_SLICE_PRIORITY:
            continue
        if not is_safe_extraction_candidate(item):
            continue
        rows.append(item)
    return sorted(rows, key=lambda item: (PREFERRED_FIRST_SLICE_PRIORITY[str(item.get("name"))], str(item.get("path"))))[:10]

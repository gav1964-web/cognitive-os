from __future__ import annotations

import ast
import builtins
import re
from typing import Any
from runtime.role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from runtime.role_skill_common import now_iso
from runtime.semantic_target_profiles import contract_for_target
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_policy import load_technical_spec_policy, policy_list, policy_rules

_BUILTIN_NAMES = set(dir(builtins))
TECHNICAL_SPEC_POLICY = load_technical_spec_policy()
CONTEXT_ONLY_SOURCE_PATH_TOKENS = policy_list(TECHNICAL_SPEC_POLICY, "context_only_source_path_tokens")
SNIPPET_POLICY = dict(TECHNICAL_SPEC_POLICY["snippet_analysis"])
CONTRACT_TYPE_POLICY = dict(TECHNICAL_SPEC_POLICY["contract_type_inference"])
SEMANTIC_RERANK_POLICY = dict(TECHNICAL_SPEC_POLICY["semantic_rerank"])
FIRST_SLICE_SCOPE_POLICY = dict(TECHNICAL_SPEC_POLICY.get("first_slice_scope") or {})
ARCHITECTURE_SHAPE_POLICY = dict(TECHNICAL_SPEC_POLICY["architecture_shape_score"])
SIDE_EFFECT_PROCESS_BOUNDARY = set(policy_list(TECHNICAL_SPEC_POLICY, "side_effect_process_boundary"))
ALLOWED_EXTERNAL_SNIPPET_NAMES = {str(item) for item in SNIPPET_POLICY.get("allowed_external_names", [])}
HIGH_CONFIDENCE_UNRESOLVED_SETS = tuple(
    frozenset(str(item) for item in row)
    for row in SNIPPET_POLICY.get("high_confidence_unresolved_sets", [])
    if isinstance(row, list)
)
IGNORED_RETURN_ANNOTATIONS = set(policy_list(CONTRACT_TYPE_POLICY, "ignored_return_annotations"))
ARGUMENT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "argument_rules")
PAYLOAD_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "payload_rules")
RESULT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "result_rules")

def _spec_traceability(
    traceability: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    by_source = _acceptance_by_source(acceptance)
    fallback_ids = [str(row.get("id") or "") for row in acceptance if isinstance(row, dict)]
    for index, row in enumerate(traceability[: len(acceptance)]):
        source = str(row.get("source") or "")
        rows.append(
            {
                "source": row.get("source"),
                "requirement": row.get("requirement"),
                "acceptance_id": by_source.get(source) or fallback_ids[min(index, len(fallback_ids) - 1)] if fallback_ids else None,
            }
        )
    return rows

def _acceptance_by_source(acceptance: list[dict[str, Any]]) -> dict[str, str]:
    result = {}
    for row in acceptance:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        item_id = str(row.get("id") or "")
        if source and item_id and source not in result:
            result[source] = item_id
    return result

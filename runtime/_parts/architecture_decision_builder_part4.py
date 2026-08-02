from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from runtime.architecture_decision_policy import load_architecture_decision_policy, policy_list, policy_rules
from runtime.local_inference import LocalInferenceConfig
from runtime.role_architect_llm import apply_architect_advisory
from runtime.role_skill_common import now_iso
from runtime.role_source_context import build_source_context

ARCHITECTURE_DECISION_POLICY = load_architecture_decision_policy()
FALLBACK_ARCHETYPE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_archetype"])
FALLBACK_SLICE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_slice"])
SOURCE_SELECTION_POLICY = dict(ARCHITECTURE_DECISION_POLICY["source_selection"])
CONTEXT_ONLY_PATH_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "context_only_path_tokens")
DOMAIN_EVIDENCE_SOURCE_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "domain_evidence_source_tokens")
PROVIDER_PARSER_FILE_GLOBS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_file_globs")
PROVIDER_PARSER_FUNCTION_MARKERS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_function_markers")
BRIEF_SORT_RULES = policy_rules(SOURCE_SELECTION_POLICY, "brief_sort_rules")

def _non_goals() -> list[str]:
    return [
        "Do not rewrite the whole project in the first transformation step.",
        "Do not mutate Capability Registry from ArchitectSkill.",
        "Do not promote generated candidates without Foundry dry-run and explicit approval.",
        "Do not replace deterministic runtime validation with role output.",
    ]

def _dedupe_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        value = row.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result

def _dedupe_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result

def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:60] or "boundary"

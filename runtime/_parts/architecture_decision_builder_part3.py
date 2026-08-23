from __future__ import annotations
import ast
from pathlib import Path
from typing import Any
from runtime.architecture_decision_policy import load_architecture_decision_policy, policy_list, policy_rules
from runtime.architecture_advisory_policy import trusted_architecture_advisory
from runtime.architecture_slice_naming import semantic_first_slice_name
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.contract_transform_contract_profiles import contract_profile_hint
from runtime.local_inference import LocalInferenceConfig
from runtime.role_architect_llm import apply_architect_advisory
from runtime.role_skill_common import now_iso
from runtime.role_source_context import build_source_context
from runtime.source_target_policy import is_context_only_implementation_target, is_fallback_product_target
from runtime.python_source_files import is_python_source_ref
ARCHITECTURE_DECISION_POLICY = load_architecture_decision_policy()
FALLBACK_ARCHETYPE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_archetype"])
FALLBACK_SLICE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_slice"])
SOURCE_SELECTION_POLICY = dict(ARCHITECTURE_DECISION_POLICY["source_selection"])
CONTEXT_ONLY_PATH_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "context_only_path_tokens")
DOMAIN_EVIDENCE_SOURCE_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "domain_evidence_source_tokens")
PROVIDER_PARSER_FILE_GLOBS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_file_globs")
PROVIDER_PARSER_FUNCTION_MARKERS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_function_markers")
BRIEF_SORT_RULES = policy_rules(SOURCE_SELECTION_POLICY, "brief_sort_rules")
def _traceability(
    tasks: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    first_slice: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        targets = list(first_slice.get("targets", []))
        rows.append(
            {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "requirement": str(step),
                "target": targets[min(index - 1, len(targets) - 1)] if targets else first_slice.get("name"),
                "acceptance": f"First slice `{first_slice.get('name')}` records and verifies step {index}: {step}",
            }
        )
    for task in tasks[:8]:
        rows.append(
            {
                "source": task.get("task_id"),
                "requirement": task.get("title"),
                "target": task.get("target"),
                "acceptance": task.get("acceptance"),
            }
        )
    for item in capabilities[:16]:
        rows.append({"source": item.get("source"), "requirement": "Capability candidate requires TechnicalSpec."})
    for risk in risks[:4]:
        rows.append({"source": risk.get("source"), "requirement": "Risk must be addressed or accepted before promotion."})
    return rows

def _architecture_synthesis(project_report: dict[str, Any]) -> dict[str, Any]:
    synthesis = project_report.get("architecture_synthesis")
    if isinstance(synthesis, dict) and synthesis:
        return dict(synthesis)
    advisory = project_report.get("architecture_synthesis_advisory")
    if trusted_architecture_advisory(advisory):
        return dict(advisory)
    content = project_report.get("content")
    if isinstance(content, dict) and isinstance(content.get("architecture_synthesis"), dict):
        return dict(content["architecture_synthesis"])
    return _fallback_architecture_synthesis(project_report)
def _fallback_architecture_synthesis(project_report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    scope = dict(answers.get("1_scope", {}))
    domain_profile = dict(scope.get("domain_profile", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    all_plan_candidates = [
        str(row.get("capability"))
        for row in list(plan.get("capabilities_to_extract", []) or [])
        if isinstance(row, dict) and row.get("capability")
    ]
    all_callable_candidates = _callable_transform_fallback_candidates(answers)
    plan_candidates = [target for target in all_plan_candidates if not is_context_only_implementation_target(target)]
    callable_candidates = [target for target in all_callable_candidates if not is_context_only_implementation_target(target)]
    candidates = callable_candidates or plan_candidates
    if not candidates:
        candidates = [target for target in [*all_callable_candidates, *all_plan_candidates] if is_fallback_product_target(target)]
    if not candidates:
        candidates = _fallback_python_read_files(summary)
    if not candidates:
        return {}
    entrypoints = [str(item) for item in list(summary.get("entrypoints", []) or []) if item]
    dataflows = [
        str(row.get("entrypoint"))
        for row in list(readiness.get("dataflows", []) or [])
        if isinstance(row, dict) and row.get("entrypoint")
    ]
    primary = candidates[0]
    return {
        "artifact_type": "ProjectArchitectureSynthesis",
        "source": "ArchitectureDecisionRecord.fallback_from_project_map_report",
        "synthesis_id": "fallback_project_map_report",
        "confidence": 0.72,
        "project_profile": {
            "archetype": _fallback_project_archetype(summary, readiness, domain_profile),
            "entrypoints": entrypoints[:6],
            "languages": list(summary.get("languages", []) or [])[:6],
            "evidence": _dedupe_strings(entrypoints + dataflows + candidates)[:12],
            "domain_profile": domain_profile,
        },
        "project_diagnosis": (
            "ProjectMapReport has runtime extraction facts but no explicit architecture_synthesis; "
            "ADR builds a conservative first slice from source-backed capability candidates."
        ),
        "target_architecture_shape": [
            "Keep entrypoint/orchestration code outside the first writable scope.",
            "Extract one source-backed capability contract before broader refactoring.",
            "Carry filesystem/network side effects behind explicit validation gates.",
        ],
        "recommended_first_slice": {
            "name": _fallback_slice_name(primary),
            "goal": str(plan.get("goal") or "Extract the first source-backed reusable capability."),
            "targets": candidates[:8],
            "target_limit": 1,
            "steps": _fallback_slice_steps(primary, plan, readiness),
            "knowledge_rule": str(FALLBACK_SLICE_POLICY.get("knowledge_rule") or "project_map_report_minimal_extraction_plan"),
        },
    }

def _fallback_project_archetype(
    summary: dict[str, Any],
    readiness: dict[str, Any],
    domain_profile: dict[str, Any] | None = None,
) -> str:
    profile_kind = str(dict(domain_profile or {}).get("kind") or "")
    if profile_kind and profile_kind != "generic":
        return profile_kind
    frameworks = {str(item).lower() for item in list(summary.get("frameworks", []) or [])}
    entrypoints = " ".join(str(item).lower() for item in list(summary.get("entrypoints", []) or []))
    dataflows = list(readiness.get("dataflows", []) or [])
    service_frameworks = set(policy_list(FALLBACK_ARCHETYPE_POLICY, "service_frameworks"))
    service_entrypoint_tokens = policy_list(FALLBACK_ARCHETYPE_POLICY, "service_entrypoint_tokens")
    if any(item in frameworks for item in service_frameworks) or any(token in entrypoints for token in service_entrypoint_tokens):
        return str(FALLBACK_ARCHETYPE_POLICY.get("service_archetype") or "python_service")
    if dataflows or any(item.endswith(".py") for item in list(summary.get("entrypoints", []) or [])):
        return str(FALLBACK_ARCHETYPE_POLICY.get("file_pipeline_archetype") or "python_cli_or_file_pipeline")
    return str(FALLBACK_ARCHETYPE_POLICY.get("generic_archetype") or "python_project")

def _fallback_slice_name(primary: str) -> str:
    name = primary.rsplit(":", 1)[-1].strip() or "first_capability"
    return f"first_slice_{_safe_id(name)}"

def _fallback_slice_steps(primary: str, plan: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    side_effects = [str(item) for item in list(plan.get("side_effects_to_isolate", []) or []) if item]
    steps = [
        str(step).format(primary=primary)
        for step in list(FALLBACK_SLICE_POLICY.get("steps") or [])
        if step
    ]
    side_effect_step = str(FALLBACK_SLICE_POLICY.get("side_effect_step") or "")
    return [
        *steps,
        *(side_effect_step.format(target=target, primary=primary) for target in side_effects[:3] if side_effect_step),
    ]

def _first_slice_contract(synthesis: dict[str, Any]) -> dict[str, Any]:
    first_slice = dict(synthesis.get("recommended_first_slice") or {})
    targets = _dedupe_strings([str(item) for item in list(first_slice.get("targets", [])) if item and not is_context_only_implementation_target(str(item))])
    steps = _dedupe_strings([str(item) for item in list(first_slice.get("steps", [])) if item])
    if not first_slice and not targets and not steps:
        return {}
    return {
        "name": semantic_first_slice_name(str(first_slice.get("name") or "first_bounded_capability_slice"), targets),
        "goal": str(first_slice.get("goal") or "Define the first bounded capability transformation."),
        "targets": targets[:8],
        "target_limit": first_slice.get("target_limit"),
        "steps": steps[:12],
        "knowledge_rule": first_slice.get("knowledge_rule"),
        "selection_policy": "choose the smallest source-backed slice that can produce a TechnicalSpec without widening writable scope",
        "handoff_expectation": "SpecWriter may reject or rerank weak targets, but must preserve this slice as evidence",
        "deferred_targets": targets[8:16],
        "source_artifact": synthesis.get("artifact_type") or "ProjectArchitectureSynthesis",
        "source": "ProjectArchitectureSynthesis.recommended_first_slice",
    }

def _architecture_synthesis_summary(synthesis: dict[str, Any]) -> dict[str, Any]:
    if not synthesis:
        return {}
    return {
        "artifact_type": synthesis.get("artifact_type"),
        "source": synthesis.get("source"),
        "synthesis_id": synthesis.get("synthesis_id"),
        "confidence": synthesis.get("confidence"),
        "project_profile": synthesis.get("project_profile", {}),
        "project_diagnosis": synthesis.get("project_diagnosis"),
        "target_architecture_shape": list(synthesis.get("target_architecture_shape", []))[:8],
    }

def _context_sources(
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> list[str]:
    values = [
        *(item.get("source") for item in capabilities),
        *(item.get("source") for item in risks),
        *(item.get("source") for item in traceability),
        *(item.get("target") for item in traceability),
    ]
    return [str(value) for value in values if value]

def _important_runtime_sources(project_report: dict[str, Any]) -> list[str]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    rows: list[str] = []
    for key in (
        "hidden_orchestrators",
        "mixed_responsibility_functions",
        "process_boundary_candidates",
        "idempotency_risks",
    ):
        for item in readiness.get(key, [])[:12]:
            if not isinstance(item, dict):
                continue
            target = item.get("target") or (
                f"{item.get('path')}:{item.get('name')}" if item.get("path") and item.get("name") else ""
            )
            if target:
                rows.append(str(target))
    rows.extend(str(row["path"]) for row in dict(readiness.get("source_strata") or {}).get("active_core", []) if isinstance(row, dict) and row.get("path"))
    for item in capabilities.get("pure_transforms", [])[:40]:
        if not isinstance(item, dict):
            continue
        target = f"{item.get('path')}:{item.get('name')}" if item.get("path") and item.get("name") else ""
        if target and _domain_evidence_source(target):
            rows.append(target)
    root = Path(str(summary.get("root") or project_report.get("root") or ""))
    rows.extend(_provider_parser_sources(root))
    return rows
def _callable_transform_fallback_candidates(answers: dict[str, Any]) -> list[str]:
    policy = CALLABLE_TRANSFORM_FALLBACK_POLICY
    if not policy.get("enabled"):
        return []
    capabilities = dict(answers.get("3_capabilities", {}))
    rows: list[str] = []
    for item in list(capabilities.get("pure_transforms", []) or [])[:80]:
        if not isinstance(item, dict):
            continue
        target = f"{item.get('path')}:{item.get('name')}" if item.get("path") and item.get("name") else ""
        if _callable_transform_fallback_target(target, item, policy=policy):
            rows.append(target)
    limit = int(policy.get("max_candidates") or 3)
    return _dedupe_strings(rows)[:limit]
def _callable_transform_fallback_target(target: str, item: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    if not _implementation_brief_source(target):
        return False
    lowered = "/" + target.replace("\\", "/").lower().lstrip("/")
    symbol = lowered.rsplit(":", 1)[-1]
    if any(token in lowered for token in list(policy.get("excluded_path_tokens") or [])):
        return False
    if any(symbol.startswith(str(prefix).lower()) for prefix in list(policy.get("excluded_symbol_prefixes") or [])):
        return False
    symbol_tokens = [str(token).lower() for token in list(policy.get("symbol_contains_any") or [])]
    path_tokens = [str(token).lower() for token in list(policy.get("path_contains_any") or [])]
    symbol_match = any(token and token in symbol for token in symbol_tokens)
    path_match = any(token and token in lowered for token in path_tokens)
    if symbol_match and path_match:
        return True
    return bool(policy.get("allow_contract_profile_without_path_match")) and _profile_compatible_transform(target, item, policy)

def _profile_compatible_transform(target: str, item: dict[str, Any], policy: dict[str, Any]) -> bool:
    args = [
        {"name": str(arg.get("name") or ""), "annotation": str(arg.get("annotation") or "")}
        for arg in list(item.get("args") or [])
        if isinstance(arg, dict)
    ]
    input_contract = {
        str(arg.get("name") or "payload"): str(arg.get("annotation") or f"Inferred{arg.get('name') or 'Payload'}")
        for arg in args
        if str(arg.get("name") or "")
    }
    output_contract = {"result": str(item.get("returns") or "InferredOutput")}
    hint = contract_profile_hint(target=target, input_contract=input_contract, output_contract=output_contract)
    profile = dict((hint or {}).get("contract_profile") or {})
    allowed = {str(value) for value in list(policy.get("pathless_allowed_contract_profiles") or [])}
    archetype = contract_archetype_for_target(target)
    allowed_archetypes = {str(value) for value in list(policy.get("pathless_allowed_contract_archetypes") or [])}
    return (bool(profile) and str(profile.get("id") or "") in allowed) or str(archetype.get("contract_family") or "") in allowed_archetypes
def _provider_parser_sources(project_root: Path) -> list[str]:
    if not project_root.exists() or not project_root.is_dir():
        return []
    rows: list[str] = []
    for file_glob in PROVIDER_PARSER_FILE_GLOBS:
        try:
            paths = list(project_root.rglob(file_glob))[:20]
        except OSError:
            continue
        for path in paths:
            rows.extend(_provider_parser_sources_from_path(project_root, path))
    return rows[:24]
def _provider_parser_sources_from_path(project_root: Path, path: Path) -> list[str]:
    rows: list[str] = []
    try:
        module = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []
    relative = path.relative_to(project_root).as_posix()
    for node in module.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if any(marker in name.lower() for marker in PROVIDER_PARSER_FUNCTION_MARKERS):
            rows.append(f"{relative}:{name}")
    return rows
def _brief_sources(
    capabilities: list[dict[str, Any]],
    source_context: dict[str, dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> list[str]:
    neighbor_sources: list[str] = []
    for item in source_context.values():
        neighbor_sources.extend(str(row) for row in item.get("callees", []) if row)
    candidates = _dedupe_strings(
        [str(item.get("source")) for item in capabilities if item.get("source")]
        + [str(item.get("source")) for item in traceability if item.get("source")]
        + list(source_context)
        + neighbor_sources
    )
    implementation = [source for source in candidates if _implementation_brief_source(source)]
    if not implementation:
        implementation = [source for source in candidates if _fallback_context_brief_source(source)]
    return sorted(
        implementation,
        key=lambda source: (0 if source in source_context else 1, *_brief_source_sort_key(source)),
    )[:32]

def _implementation_brief_source(source: str) -> bool:
    if not is_python_source_ref(source):
        return False
    return not is_context_only_implementation_target(source)
def _fallback_context_brief_source(source: str) -> bool:
    return is_python_source_ref(source) and ":" in source and is_fallback_product_target(source)
def _fallback_python_read_files(summary: dict[str, Any]) -> list[str]:
    rows = []
    for item in list(summary.get("read_files") or []):
        source = str(item or "").replace("\\", "/")
        lowered = "/" + source.lower().lstrip("/")
        policy_allowed = any(token in lowered for token in FALLBACK_READ_FILE_PATH_TOKENS)
        if ("/" in source and not policy_allowed) or not is_python_source_ref(source):
            continue
        if any(token in lowered for token in CONTEXT_ONLY_PATH_TOKENS):
            continue
        rows.append(source)
    return _dedupe_strings(rows)[:4]
def _domain_evidence_source(source: str) -> bool:
    lowered = source.lower()
    return any(token in lowered for token in DOMAIN_EVIDENCE_SOURCE_TOKENS)
def _brief_source_sort_key(source: str) -> tuple[int, str]:
    lowered = source.lower()
    score = 0
    for rule in BRIEF_SORT_RULES:
        tokens = [str(token).lower() for token in list(rule.get("tokens") or [])]
        if any(token in lowered for token in tokens):
            score += int(rule.get("score_delta") or 0)
    return (score, source)
def _tasks(project_report: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = dict(project_report.get("analysis_tasks", {})).get("tasks", [])
    return [item for item in tasks if isinstance(item, dict)]
def _targets_by_type(tasks: list[dict[str, Any]], types: set[str]) -> list[str]:
    return [str(task.get("target")) for task in tasks if task.get("type") in types and task.get("target")]
def _node_refs(rows: object) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("path") and row.get("name"):
            refs.append(f"{row.get('path')}:{row.get('name')}")
    return refs
def _plan_capability_refs(readiness: dict[str, Any]) -> list[str]:
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    rows = plan.get("capabilities_to_extract", [])
    if not isinstance(rows, list):
        return []
    return [str(row.get("capability")) for row in rows if isinstance(row, dict) and row.get("capability")]
def _decision_summary(summary: dict[str, Any], capabilities: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    project = summary.get("root", "project")
    return f"Treat {project} as a candidate for bounded capability extraction: {len(capabilities)} capability candidates, {len(risks)} architecture risks."
def _source_strata(readiness: dict[str, Any]) -> dict[str, Any]:
    strata = readiness.get("source_strata", {})
    if not isinstance(strata, dict):
        return {}
    return {
        "active_core": list(strata.get("active_core", []))[:24],
        "legacy_noise": list(strata.get("legacy_noise", []))[:24],
        "context_only": list(strata.get("context_only", []))[:24],
        "packaged_copy": list(strata.get("packaged_copy", []))[:24],
        "policy": "Use active_core for first extraction candidates; keep legacy_noise/context_only as evidence, not first targets.",
    }

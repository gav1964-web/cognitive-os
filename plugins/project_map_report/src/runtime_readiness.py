"""Runtime extraction readiness heuristics for project map reports."""

from __future__ import annotations

from typing import Any

from .core_paths import classify_source_path, is_core_path
from .runtime_readiness_helpers import (
    all_functions,
    boundary_function_candidates,
    data_structures,
    flow_confidence,
    flow_steps,
    function_evidence,
    is_safe_extraction_candidate,
    responsibilities,
    safe_node_id,
    weak_contract_zones,
)


def data_lifecycle(
    project_type: str,
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    python_structure: dict[str, Any],
) -> list[dict[str, str]]:
    schemas = dict(python_structure.get("contracts", {})).get("schema_like_classes", [])
    schema_refs = [f"{item.get('path')}:{item.get('name')}" for item in schemas[:3]]
    schema_hint = f"schema objects ({', '.join(schema_refs)})" if schema_refs else "dict/string payloads"
    if routes:
        return [
            {"stage": "input", "shape": "HTTP request", "evidence": f"{len(routes)} detected routes"},
            {"stage": "validation", "shape": schema_hint, "evidence": "schema-like classes/type hints when present"},
            {"stage": "processing", "shape": "handler/core function arguments", "evidence": "route handlers and central flow nodes"},
            {"stage": "output", "shape": "HTTP response / JSON-like object", "evidence": project_type},
        ]
    if commands:
        return [
            {"stage": "input", "shape": "CLI/script arguments and local files", "evidence": f"{len(commands)} runtime command groups"},
            {"stage": "processing", "shape": "Python function arguments / intermediate artifacts", "evidence": "entrypoint workflow"},
            {"stage": "output", "shape": "filesystem artifacts, stdout/stderr, or reports", "evidence": "script side effects"},
        ]
    return [{"stage": "unknown", "shape": "not enough evidence", "evidence": "no routes or runtime commands detected"}]


def best_effort_dataflows(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    flows = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        calls = [str(call) for call in fn.get("calls", [])]
        steps = flow_steps(fn, calls)
        if len(steps) < 2:
            continue
        flows.append(
            {
                "entrypoint": f"{fn.get('path')}:{fn.get('name')}",
                "confidence": flow_confidence(steps),
                "flow": steps,
            }
        )
    return sorted(flows, key=lambda item: (-len(item["flow"]), item["entrypoint"]))[:12]


def source_strata(python_structure: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, dict[str, str]] = {}
    for file_row in python_structure.get("files", []):
        path = str(file_row.get("path") or "")
        if path:
            classified = classify_source_path(path)
            rows[path] = classified
        for fn in file_row.get("functions", []):
            fn_path = str(fn.get("path") or path)
            if fn_path and fn_path not in rows:
                rows[fn_path] = classify_source_path(fn_path)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows.values():
        grouped.setdefault(row["kind"], []).append(row)
    return {
        "active_core": sorted(grouped.get("active_core", []), key=_source_strata_sort_key)[:24],
        "legacy_noise": sorted(grouped.get("legacy_noise", []), key=_source_strata_sort_key)[:24],
        "context_only": sorted(grouped.get("context_only", []), key=_source_strata_sort_key)[:24],
        "packaged_copy": sorted(grouped.get("packaged_copy", []), key=_source_strata_sort_key)[:24],
    }


def _source_strata_sort_key(item: dict[str, str]) -> tuple[int, str]:
    path = item.get("path", "")
    lowered = path.lower()
    priority_tokens = ("family_registry", "/pipeline.py", "/main.py", "app/core/cache.py")
    if any(token in path for token in priority_tokens):
        priority = 0
    elif lowered.startswith("src/"):
        priority = 1
    elif lowered.startswith(("app/", "lib/", "packages/")):
        priority = 2
    else:
        priority = 3
    return (priority, path)


def evidence_claims(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        target = f"{fn.get('path')}:{fn.get('name')}"
        fn_responsibilities = responsibilities(fn)
        if len(fn_responsibilities) >= 3:
            claims.append(
                {
                    "claim": f"{target} mixes responsibilities",
                    "kind": "mixed_responsibility",
                    "evidence": function_evidence(fn, fn_responsibilities),
                    "confidence": min(0.95, 0.55 + len(fn_responsibilities) * 0.08),
                }
            )
        effects = set(fn.get("side_effects", []))
        if effects:
            claims.append(
                {
                    "claim": f"{target} has side effects",
                    "kind": "side_effect",
                    "evidence": function_evidence(fn, sorted(effects)),
                    "confidence": 0.8,
                }
            )
    return claims[:20]


def mixed_responsibility_functions(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        fn_responsibilities = responsibilities(fn)
        if len(fn_responsibilities) < 3:
            continue
        rows.append(
            {
                "path": fn.get("path"),
                "name": fn.get("name"),
                "line": fn.get("line"),
                "loc": fn.get("loc"),
                "responsibilities": fn_responsibilities,
                "reason": "mixed_io_decision_error_formatting_or_state",
            }
        )
    return sorted(rows, key=lambda item: (-len(item["responsibilities"]), -int(item.get("loc") or 0), str(item.get("path"))))[:12]


def hidden_orchestrators(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    obvious = ("manager", "controller", "runner", "orchestrator", "main")
    orchestration_tokens = ("dispatch", "pipeline", "process", "scrape", "loop", "worker", "handle")
    route_functions = {str(route.get("function")) for route in python_structure.get("routes", []) if route.get("function")}
    rows = []
    for node in python_structure.get("central_nodes", []):
        if not is_core_path(str(node.get("path", ""))):
            continue
        name = str(node.get("name", "")).lower()
        if str(node.get("name")) in route_functions or name.startswith("legacy"):
            continue
        if any(token in name for token in obvious):
            continue
        call_count = int(node.get("call_count") or 0)
        loc = int(node.get("loc") or 0)
        token_match = any(token in name for token in orchestration_tokens)
        if call_count < 5 and loc < 60 and not (token_match and call_count >= 3):
            continue
        rows.append({**node, "reason": "high_call_count_or_large_control_surface_without_orchestrator_name"})
    return rows[:10]


def long_lived_state(imports: set[str], stack: dict[str, Any], python_structure: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    if imports & {"sqlite3", "sqlalchemy"}:
        rows.append({"kind": "database", "evidence": ", ".join(sorted(imports & {"sqlite3", "sqlalchemy"})), "checkpoint_need": "database version/transaction boundary"})
    if imports & {"functools", "cachetools", "diskcache"}:
        rows.append({"kind": "cache", "evidence": ", ".join(sorted(imports & {"functools", "cachetools", "diskcache"})), "checkpoint_need": "cache key/input hash"})
    if imports & {"tempfile", "pathlib", "os", "shutil"}:
        rows.append({"kind": "filesystem/temp files", "evidence": ", ".join(sorted(imports & {"tempfile", "pathlib", "os", "shutil"})), "checkpoint_need": "artifact manifest/checksums"})
    if imports & {"queue", "asyncio", "threading", "concurrent"}:
        rows.append({"kind": "queue/session/concurrency state", "evidence": ", ".join(sorted(imports & {"queue", "asyncio", "threading", "concurrent"})), "checkpoint_need": "job id/progress/lease"})
    for fn in all_functions(python_structure):
        calls = " ".join(str(call).lower() for call in fn.get("calls", []))
        if any(token in calls for token in ("cache", "session", "queue", "sqlite", "write_text", "dump")):
            rows.append({"kind": "function-level state mutation", "evidence": f"{fn.get('path')}:{fn.get('name')}", "checkpoint_need": "persist before/after state"})
    if stack.get("large_artifacts"):
        rows.append({"kind": "large artifacts", "evidence": "large_artifacts detected", "checkpoint_need": "artifact manifest/checksums"})
    return rows[:12] or [{"kind": "not enough evidence", "evidence": "no persistent-state imports/calls detected", "checkpoint_need": "manual audit"}]


def idempotency_risks(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    risky_verbs = ("write", "save", "create", "delete", "remove", "send", "post", "commit", "insert", "update", "publish")
    route_functions = {str(route.get("function")) for route in python_structure.get("routes", []) if route.get("function")}
    rows = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        name = str(fn.get("name", "")).lower()
        calls = " ".join(str(call).lower() for call in fn.get("calls", []))
        runtime_calls = " ".join(
            call for call in calls.split() if call not in {"app.post", "app.get", "app.put", "app.delete", "app.patch", "app.route"}
        )
        effects = set(fn.get("side_effects", []))
        if str(fn.get("name")) in route_functions and not effects and not any(verb in runtime_calls for verb in risky_verbs):
            continue
        if effects <= {"filesystem", "filesystem_read"} and any(name.startswith(prefix) for prefix in ("load", "read", "fetch")):
            continue
        if not effects and any(token in name for token in ("main", "pipeline", "loop", "scrape")):
            continue
        if effects & {"filesystem", "database", "network", "subprocess", "memory_state"} or any(verb in name or verb in runtime_calls for verb in risky_verbs):
            if effects <= {"filesystem_read"} and not any(verb in name or verb in runtime_calls for verb in risky_verbs):
                continue
            rows.append(
                {
                    "target": f"{fn.get('path')}:{fn.get('name')}",
                    "side_effects": sorted(effects),
                    "risk": "retry_or_replay_may_duplicate_side_effects",
                    "mitigation": "require idempotency key, output existence check, transaction boundary, or dry-run mode",
                }
            )
    return rows[:12]


def quarantine_candidates(
    risks: list[dict[str, str]],
    imports: set[str],
    python_structure: dict[str, Any],
) -> list[dict[str, str]]:
    rows = []
    for risk in risks:
        if risk.get("code") in {"unpinned_dependencies", "risky_imports", "large_artifacts", "tree_scan_truncated"}:
            rows.append({"target": risk.get("code", ""), "reason": risk.get("detail", ""), "policy": "mark failed capability degraded/quarantined on matching runtime failure"})
    if imports & {"requests", "httpx", "openai", "gigachat"}:
        rows.append({"target": "external_api", "reason": ", ".join(sorted(imports & {"requests", "httpx", "openai", "gigachat"})), "policy": "timeout/rate-limit/API drift quarantine"})
    if imports & {"subprocess"}:
        rows.append({"target": "subprocess", "reason": "subprocess import detected", "policy": "process timeout and captured stderr quarantine"})
    for detail in dict(python_structure.get("project_insights", {})).get("error_handling", {}).get("functions_with_try", [])[:5]:
        rows.append({"target": detail, "reason": "explicit try/except boundary", "policy": "convert repeated dependency/parser errors into interrupt"})
    return rows[:12] or [{"target": "manual_audit", "reason": "no obvious quarantine candidates", "policy": "observe first failures"}]


def process_boundary_candidates(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for fn in all_functions(python_structure):
        if not is_core_path(str(fn.get("path", ""))):
            continue
        effects = set(fn.get("side_effects", []))
        calls = " ".join(str(call).lower() for call in fn.get("calls", []))
        reasons = []
        if "subprocess" in effects or "subprocess" in calls:
            reasons.append("subprocess")
        if "network" in effects:
            reasons.append("network_timeout")
        if int(fn.get("loc") or 0) >= 120:
            reasons.append("large_function")
        if "database" in effects:
            reasons.append("database_side_effect")
        if not reasons:
            continue
        rows.append({"target": f"{fn.get('path')}:{fn.get('name')}", "reasons": reasons, "policy": "prefer process boundary with timeout and captured artifacts"})
    return rows[:12]


def contract_test_strategy(python_structure: dict[str, Any]) -> dict[str, Any]:
    pure = [
        f"{item.get('path')}:{item.get('name')}"
        for item in python_structure.get("pure_transform_candidates", [])
        if is_core_path(str(item.get("path", "")))
    ][:8]
    weak = weak_contract_zones(python_structure)[:8]
    error_functions = dict(python_structure.get("project_insights", {})).get("error_handling", {}).get("functions_with_try", [])[:8]
    return {
        "auto_contract_tests": pure,
        "schema_seeded_tests": data_structures(python_structure)[:8],
        "hand_written_negative_tests": sorted(set(weak + error_functions))[:12],
    }


def resume_reuse_plan(routes: list[dict[str, Any]], commands: list[dict[str, Any]], imports: set[str]) -> list[dict[str, str]]:
    if routes:
        return [
            {"step": "request_capture", "reuse": "yes", "reason": "raw request can be replayed"},
            {"step": "validation", "reuse": "yes_if_schema_version_same", "reason": "validated payload can be checkpointed"},
            {"step": "external_provider_call", "reuse": "cache_if_pure_response", "reason": "avoid duplicate network/API side effects"},
            {"step": "response_formatting", "reuse": "recompute", "reason": "cheap deterministic formatting"},
        ]
    if commands:
        return [
            {"step": "input_discovery", "reuse": "yes", "reason": "file list/config snapshot can be checkpointed"},
            {"step": "parsed_intermediate", "reuse": "yes_if_input_hash_same", "reason": "parsed artifacts can be cached"},
            {"step": "write_or_publish", "reuse": "no_without_idempotency_key", "reason": "side effects may duplicate"},
        ]
    if imports & {"requests", "httpx", "openai", "gigachat"}:
        return [
            {"step": "external_api_response", "reuse": "cache_if_request_hash_same", "reason": "protect retry/replay from duplicate cost and drift"},
            {"step": "input_discovery", "reuse": "yes", "reason": "filesystem/config inputs can be snapshotted"},
            {"step": "write_or_publish", "reuse": "no_without_idempotency_key", "reason": "filesystem/process side effects may duplicate"},
        ]
    if imports & {"pathlib", "os", "json", "csv", "subprocess", "asyncio", "queue", "threading"}:
        return [
            {"step": "input_discovery", "reuse": "yes", "reason": "filesystem/config inputs can be snapshotted"},
            {"step": "parsed_intermediate", "reuse": "yes_if_input_hash_same", "reason": "parsed artifacts can be cached"},
            {"step": "write_or_publish", "reuse": "no_without_idempotency_key", "reason": "filesystem/process side effects may duplicate"},
            {"step": "manual", "reuse": "unknown", "reason": "no explicit runtime command or route was detected"},
        ]
    return [{"step": "manual", "reuse": "unknown", "reason": "not enough execution evidence"}]


def minimal_extraction_plan(
    python_structure: dict[str, Any],
    routes: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    plan = []
    route_functions = {str(route.get("function")) for route in routes if route.get("function")}
    for item in python_structure.get("pure_transform_candidates", []):
        if not is_core_path(str(item.get("path", ""))):
            continue
        if not is_safe_extraction_candidate(item):
            continue
        if any(token in str(item.get("name", "")).lower() for token in ("loop", "pipeline", "scrape", "dispatch")):
            continue
        if str(item.get("name")) in route_functions:
            continue
        plan.append({"capability": f"{item.get('path')}:{item.get('name')}", "why": "pure transform candidate", "first_contract": "derive from signature/type hints"})
        if len([row for row in plan if row["why"] == "pure transform candidate"]) >= 3:
            break
    for item in boundary_function_candidates(python_structure)[:4]:
        if not is_safe_extraction_candidate(item):
            continue
        capability = f"{item.get('path')}:{item.get('name')}"
        if any(row["capability"] == capability for row in plan):
            continue
        plan.append({"capability": capability, "why": "I/O or runtime boundary candidate", "first_contract": "input/output artifact contract"})
    wide_added = 0
    for item in python_structure.get("wide_functions", []):
        if not is_core_path(str(item.get("path", ""))):
            continue
        if not is_safe_extraction_candidate(item):
            continue
        plan.append({"capability": f"{item.get('path')}:{item.get('name')}", "why": "broad function to split", "first_contract": "wrap current input/output before cutting internals"})
        wide_added += 1
        if wide_added >= 3:
            break
    capabilities = plan[:8]
    blocked_by = [] if capabilities else ["no_safe_python_candidate"]
    return {
        "goal": "Build first Cognitive OS pipeline from this project",
        "capabilities_to_extract": capabilities,
        "runtime_needed": ["Pipeline DSL", "checkpoint/replay", "contract validation"],
        "contracts_to_write": [item["first_contract"] for item in capabilities[:5]],
        "side_effects_to_isolate": [str(item.get("target")) for item in idempotency_risks(python_structure)[:5]],
        "first_pipeline_dsl_candidate": {
            "nodes": [{"id": safe_node_id(item["capability"]), "capability": item["capability"]} for item in capabilities[:5]],
            "edges": [],
        },
        "blocked_by": blocked_by,
    }

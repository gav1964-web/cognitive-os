"""Config-backed typed contract families and AST recognition."""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "self_improvement_contract_families.json"


@lru_cache(maxsize=1)
def load_contract_families(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_improvement_contract_families.v1":
        raise ValueError("self-improvement contract families schema mismatch")
    for family_id, family in dict(payload.get("families") or {}).items():
        required = ("input_contract", "output_contract", "side_effect_policy", "validation_gates", "failure_modes")
        if any(not family.get(field) for field in required):
            raise ValueError(f"contract family {family_id} lacks typed evidence")
    return payload


def recognize_contract_family(node: ast.AsyncFunctionDef | ast.FunctionDef) -> tuple[str, dict[str, bool]] | None:
    recognizers = (
        ("dynamic_method_dispatch_boundary", _dynamic_dispatch_evidence),
        ("external_service_state_sync_boundary", _sync_evidence),
        ("file_extension_admission_policy", _file_admission_evidence),
        ("route_tree_flatten_boundary", _route_flatten_evidence),
        ("persistence_append_command", _persistence_append_evidence),
    )
    for family_id, recognizer in recognizers:
        evidence = recognizer(node)
        if evidence and all(evidence.values()):
            return family_id, evidence
    return None


def family_profile(family_id: str, evidence: dict[str, bool]) -> dict[str, Any]:
    family = dict(dict(load_contract_families()["families"])[family_id])
    return {"contract_family": family_id, **family, "score_bonus": 0, "ranking_bonus": 0, "training_evidence": evidence}


def _dynamic_dispatch_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    selectors = {arg.arg.lower() for arg in node.args.args if arg.arg not in {"self", "cls"}}
    dynamic_calls = [
        item for item in ast.walk(node)
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Call)
        and _call_name(item.func.func).lower() == "getattr"
    ]
    return {
        "selector_input": bool(selectors & {"method", "action", "handler", "operation"}),
        "receiver_lookup": any(call.func.args and isinstance(call.func.args[0], ast.Name) and call.func.args[0].id in {"self", "cls"} for call in dynamic_calls),
        "selector_lookup": any(len(call.func.args) > 1 and isinstance(call.func.args[1], ast.Name) and call.func.args[1].id.lower() in selectors for call in dynamic_calls),
        "request_values_forwarded": any(any(keyword.arg is None and "request" in ast.unparse(keyword.value).lower() for keyword in call.keywords) for call in dynamic_calls),
        "delegated_result": any(isinstance(item, ast.Return) and item.value in dynamic_calls for item in ast.walk(node)),
        "bounded_body": len(list(ast.walk(node))) <= 40,
    }


def _sync_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    calls = _calls(node)
    mutations = any(isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for item in ast.walk(node))
    dictionary_return = any(isinstance(item, ast.Return) and isinstance(item.value, ast.Dict) for item in ast.walk(node))
    annotated_mapping = bool(node.returns and "dict" in ast.unparse(node.returns).lower())
    return {
        "async_orchestration": isinstance(node, ast.AsyncFunctionDef) and _has(node, ast.Await),
        "sync_intent": node.name.lower().startswith(("sync_", "import_", "refresh_", "reconcile_")),
        "external_io": any(token in call for call in calls for token in ("client", "fetch", "get_messages", "iter_messages", "get_entity")),
        "state_boundary": mutations and any(token in call for call in calls for token in ("commit", "flush", "execute", "upsert")),
        "failure_boundary": _has(node, ast.Try) or _has(node, ast.Raise),
        "structured_result": dictionary_return or annotated_mapping,
    }


def _file_admission_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    text = ast.unparse(node).lower()
    args = {arg.arg.lower() for arg in node.args.args}
    return {
        "file_input": bool(args & {"filename", "file_name", "name"}),
        "extension_operation": "rsplit" in text or "splitext" in text or "suffix" in text,
        "allow_set_comparison": "allowed" in text and " in " in text,
        "normalization": ".lower()" in text or ".casefold()" in text,
        "boolean_result": any(isinstance(item, ast.Return) and isinstance(item.value, (ast.BoolOp, ast.Compare)) for item in ast.walk(node)),
        "side_effect_free": not _has(node, (ast.Assign, ast.AugAssign, ast.Await, ast.Raise, ast.Yield)),
    }


def _route_flatten_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    text = ast.unparse(node).lower()
    args = {arg.arg.lower() for arg in node.args.args}
    return {
        "route_input": "routes" in args,
        "generator_output": _has(node, (ast.Yield, ast.YieldFrom)),
        "route_iteration": "for " in text and "route" in text,
        "compatibility_branch": _has(node, ast.If) and any(token in text for token in ("iter_route_contexts", "effective_route_contexts", "starlette")),
        "matchable_projection": "matchable_route" in text or "yield starlette_route" in text,
        "side_effect_free": not _has(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Await, ast.Raise)),
    }


def _persistence_append_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    calls = _calls(node)
    args = {arg.arg.lower() for arg in node.args.args}
    return {
        "command_intent": node.name.lower().startswith(("add_", "append_", "create_", "insert_")),
        "unit_of_work_input": bool(args & {"session", "db", "unit_of_work", "uow"}),
        "record_construction": any(isinstance(item, ast.Assign) and isinstance(item.value, ast.Call) for item in ast.walk(node)),
        "append_call": any(call.endswith(".add") or call.endswith(".append") for call in calls),
        "void_result": not any(isinstance(item, ast.Return) and item.value is not None for item in ast.walk(node)),
        "bounded_body": len(list(ast.walk(node))) <= 80,
    }


def _calls(node: ast.AST) -> list[str]:
    return [_call_name(item.func).lower() for item in ast.walk(node) if isinstance(item, ast.Call)]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


def _has(node: ast.AST, kinds: Any) -> bool:
    return any(isinstance(item, kinds) for item in ast.walk(node))

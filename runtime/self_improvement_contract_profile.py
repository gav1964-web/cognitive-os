"""Evidence-bound temporary contract profile synthesis."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


def synthesize_contract_profile(project_dir: Path, source: str) -> dict[str, Any] | None:
    """Recognize a supported contract family from source evidence, never LLM scoring."""
    path_text, separator, symbol = source.partition(":")
    path = (project_dir / path_text).resolve()
    if not separator or not _within(path, project_dir.resolve()) or not path.is_file():
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return None
    node = _function(tree, symbol)
    if node is None:
        return None
    evidence = _sync_evidence(node)
    if not all(evidence.values()):
        return None
    identity = hashlib.sha256(f"{path_text}:{symbol}".encode()).hexdigest()[:12]
    return {
        "id": f"training_external_service_state_sync_{identity}",
        "contract_family": "external_service_state_sync_boundary",
        "symbols": [symbol.lower()],
        "path_contains_any": [path_text.replace("\\", "/").lower()],
        "input_contract": {
            "request": "ExternalSyncRequest(actor, scope, options?)",
            "dependencies": "ExternalSyncDependencies(client, state_store, clock?, rate_gate?)",
        },
        "output_contract": {
            "result": "ExternalSyncResult(created_count, updated_count, affected_ids?, warnings?)",
            "failure_packet": "ExternalSyncFailure(kind, retry_after?, evidence_ref)",
        },
        "side_effect_policy": {
            "external_io": "external calls, retries and rate limits are explicit",
            "state_mutation": "local mutations and commit boundary are observable",
            "requires_validation_gate": True,
        },
        "validation_gates": [
            "empty input and successful synchronization return structured counts",
            "external failure and rate limit behavior are bounded",
            "state writes and commit boundary are explicit and idempotency is reviewed",
        ],
        "failure_modes": ["external_service_failure", "rate_limited", "partial_state_write", "invalid_session"],
        "score_bonus": 0,
        "ranking_bonus": 0,
        "reason": "AST proves an external-service synchronization orchestration contract",
        "training_evidence": evidence,
    }


def _function(tree: ast.AST, symbol: str) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name.lower() == symbol.lower():
            return node
    return None


def _sync_evidence(node: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, bool]:
    calls = [_call_name(item.func).lower() for item in ast.walk(node) if isinstance(item, ast.Call)]
    mutations = any(isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for item in ast.walk(node))
    dictionary_return = any(
        isinstance(item, ast.Return) and isinstance(item.value, ast.Dict) for item in ast.walk(node)
    )
    annotated_mapping = bool(node.returns and "dict" in ast.unparse(node.returns).lower())
    return {
        "async_orchestration": isinstance(node, ast.AsyncFunctionDef) and any(isinstance(item, ast.Await) for item in ast.walk(node)),
        "sync_intent": node.name.lower().startswith(("sync_", "import_", "refresh_", "reconcile_")),
        "external_io": any(token in call for call in calls for token in ("client", "fetch", "get_messages", "iter_messages", "get_entity")),
        "state_boundary": mutations and any(token in call for call in calls for token in ("commit", "flush", "execute", "upsert")),
        "failure_boundary": any(isinstance(item, (ast.Try, ast.Raise)) for item in ast.walk(node)),
        "structured_result": dictionary_return or annotated_mapping,
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

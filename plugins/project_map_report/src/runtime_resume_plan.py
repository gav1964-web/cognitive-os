"""Resume/reuse heuristics for runtime readiness reports."""

from __future__ import annotations

from typing import Any


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

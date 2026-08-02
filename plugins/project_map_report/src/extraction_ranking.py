"""First-slice extraction candidate ranking."""

from __future__ import annotations

from typing import Any


def add_extraction_candidate(
    candidates: dict[str, dict[str, Any]],
    item: dict[str, Any],
    level: str,
    why: str,
) -> None:
    capability = f"{item.get('path')}:{item.get('name')}"
    if capability == ":":
        return
    score = extraction_candidate_score(item, level)
    first_contract = "input/output artifact contract"
    if level == "helper_transform":
        first_contract = "derive from signature/type hints"
    elif level == "broad_split":
        first_contract = "wrap current input/output before cutting internals"
    row = {
        "capability": capability,
        "why": why,
        "reason": why,
        "candidate_level": level,
        "candidate_score": score,
        "first_contract": first_contract,
    }
    existing = candidates.get(capability)
    if not existing or score > int(existing.get("candidate_score") or 0):
        candidates[capability] = row


def extraction_candidate_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (-int(row["candidate_score"]), level_rank(str(row["candidate_level"])), str(row["capability"]))


def extraction_candidate_score(item: dict[str, Any], level: str) -> int:
    name = str(item.get("name") or "").lower()
    loc = int(item.get("loc") or 0)
    call_count = int(item.get("call_count") or len(item.get("calls", [])) or 0)
    effects = set(item.get("side_effects", []) or [])
    score = {
        "core_flow": 80,
        "boundary": 70,
        "broad_split": 65,
        "preferred_anchor": 55,
        "helper_transform": 40,
    }.get(level, 30)
    score += min(loc, 160) // 16
    score += min(call_count, 24)
    if effects:
        score -= 12
    score += domain_contract_score(name, str(item.get("path") or ""))
    if is_trivial_helper_name(name):
        score -= 35
    if is_low_value_first_slice_name(name, str(item.get("path") or "")):
        score -= 45
    if is_whole_workflow_wrapper_name(name):
        score -= 42
    if is_mutation_like_first_slice_name(name):
        score -= 30
    if name.startswith("_") and level != "core_flow":
        score -= 10
    if any(token in name for token in ("handle", "process", "dispatch", "build", "create", "resolve", "validate", "parse")):
        score += 8
    if "_llm_client.py" in str(item.get("path") or "").replace("\\", "/").lower() and any(
        token in name for token in ("normalize", "parse", "extract", "curl_fallback", "fetch_available_models")
    ):
        score += 34
    if str(item.get("path") or "").replace("\\", "/").lower().endswith("service.py") and name == "resolve":
        score += 35
    return score


def is_trivial_helper_name(name: str) -> bool:
    if name in {"flush", "match", "storage", "no_color", "capabilities", "all", "any", "get"}:
        return True
    if any(token in name for token in ("cache_key", "build_key", "memcache_key", "get_path_for_link")):
        return True
    if name.startswith(("is_", "has_", "to_", "from_", "get_")):
        return True
    return False


def is_low_value_first_slice_name(name: str, path: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    if name == "__init__" or normalized_path.endswith("/__init__.py"):
        return True
    if name == "describe_module":
        return False
    if name == "build_plugin_metadata":
        return True
    if name in {"configure_logging", "setup_logging", "basic_config", "set_loglevel"}:
        return True
    if name in {"config", "configure", "settings"}:
        return True
    return False


def is_whole_workflow_wrapper_name(name: str) -> bool:
    if name in {"scrape", "run_pipeline", "pipeline", "run_workflow", "process_all", "worker", "lifespan"}:
        return True
    if name in {"run_import_job"}:
        return False
    return name.startswith(("run_", "scrape_", "pipeline_")) and not any(
        token in name for token in ("parse", "validate", "normalize", "resolve", "build")
    )


def is_mutation_like_first_slice_name(name: str) -> bool:
    if name in {"write", "save", "delete", "remove", "drop", "insert", "update", "commit", "flush"}:
        return True
    return name.startswith(("write_", "save_", "delete_", "remove_", "drop_", "insert_", "update_"))


def domain_contract_score(name: str, path: str) -> int:
    normalized_path = path.replace("\\", "/").lower()
    score = 0
    query_names = {"search", "where", "filter", "matches", "evaluate", "compile_query", "parse_query"}
    if name in query_names or any(token in name for token in ("query", "condition", "predicate")):
        score += 30
    if "queries.py" in normalized_path and name not in {"all", "any", "match"}:
        score += 18
    if name == "get":
        score -= 18
    if "storages.py" in normalized_path or "/storage" in normalized_path:
        score -= 18
    if "middlewares.py" in normalized_path or "middleware.py" in normalized_path:
        score -= 28
    if _is_llm_service_boundary(name, normalized_path):
        score += 54
    if "helpers.py" in normalized_path and any(token in name for token in ("key", "name", "path", "value")):
        score -= 24
    if _is_config_loader(name, normalized_path):
        score += 52
    if _is_provider_adapter_boundary(name, normalized_path):
        score += 46
    if _is_llm_gateway_boundary(name, normalized_path):
        score += 58
    if _is_llm_cache_or_model_policy(name, normalized_path):
        score += 50
    if _is_classifier_boundary(name, normalized_path):
        score += 38
    if _is_server_lifecycle_wrapper(name, normalized_path):
        score -= 40
    if _is_route_alias_resolver(name, normalized_path):
        score -= 28
    if _is_low_level_download_tile(name, normalized_path):
        score -= 32
    if _is_api_facade_over_service(name, normalized_path):
        score -= 36
    if _is_raw_llm_payload_helper(name):
        score -= 30
    if _is_runtime_resource_probe(name):
        score += 42
    if _is_live_provider_call(name, normalized_path):
        score -= 34
    if _is_generated_version_descriptor_noise(name, normalized_path):
        score -= 48
    if any(token in normalized_path for token in ("trigger_dag", "taskinstance", "task_engine", "scheduler_job")):
        score += 22
    if any(part in normalized_path for part in ("/external-deps/", "/vendor/", "/vendored/", "/third_party/", "/waflib/")):
        score -= 55
    score += _domain_signal_score(
        name,
        normalized_path,
        {
            "workflow": ("dag", "flow", "task", "scheduler", "trigger", "state", "worker"),
            "automation": ("playbook", "inventory", "module", "task", "template", "connection", "execute"),
            "archive": ("archive", "repository", "manifest", "chunk", "restore", "backup"),
            "packaging": ("analysis", "hook", "spec", "bundle", "bootloader", "modulegraph"),
            "proxy": ("proxy", "flow", "cert", "tls", "intercept", "websocket"),
            "gui": ("plugin", "widget", "editor", "lsp", "workspace", "preferences"),
            "ml_ui": ("component", "blocks", "interface", "queue", "api", "predict"),
            "dataflow": ("graph", "blockwise", "scheduler", "array", "dataframe", "partition"),
        },
    )
    return score


def _is_config_loader(name: str, path: str) -> bool:
    return "config" in path and name in {"load_config", "read_config", "parse_config", "resolve_config"}


def _is_provider_adapter_boundary(name: str, path: str) -> bool:
    return any(token in path for token in ("/providers/", "/adapters", "/provider_", "providers.py", "llm_providers.py")) and any(
        token in name for token in ("generate", "adapt", "build", "create", "call", "load", "resolve")
    )


def _is_llm_gateway_boundary(name: str, path: str) -> bool:
    if name.startswith(("_ensure_", "ensure_", "_resolve_", "resolve_")):
        return False
    text = f"{path}:{name}"
    if not any(token in text for token in ("api_server.py", "gigachat_client.py", "llm_provider", "llm_providers", "providers")):
        return False
    return any(
        token in name
        for token in (
            "chat",
            "completion",
            "generate",
            "get_answer",
            "load_providers",
            "call_provider",
            "provider",
            "arena",
            "stream",
        )
    )


def _is_llm_cache_or_model_policy(name: str, path: str) -> bool:
    text = f"{path}:{name}"
    if not any(token in text for token in ("api_server.py", "gigachat_client.py", "llm_provider", "llm_providers", "cache", "model")):
        return False
    return any(token in name for token in ("cache", "model", "classify", "select", "bypass"))


def _is_llm_service_boundary(name: str, path: str) -> bool:
    text = f"{path}:{name}"
    if "/services/" not in path:
        return False
    return any(token in text for token in ("context", "fallback", "llm", "provider", "token", "truncate", "summarize"))


def _is_classifier_boundary(name: str, path: str) -> bool:
    return any(token in path for token in ("/judge", "/classifier", "/complexity")) and any(
        token in name for token in ("classify", "assess", "score")
    )


def _is_server_lifecycle_wrapper(name: str, path: str) -> bool:
    return ("/server.py" in path or "/app.py" in path) and (
        name == "lifespan" or name.startswith(("_ensure_", "_resolve_", "ensure_", "resolve_"))
    )


def _is_route_alias_resolver(name: str, path: str) -> bool:
    return "/routing.py" in path and name.startswith("resolve_") and "execute" not in name


def _is_low_level_download_tile(name: str, path: str) -> bool:
    return "download_tile" in name or ("download_tiles.py" in path and name.startswith("download"))


def _is_api_facade_over_service(name: str, path: str) -> bool:
    return path.endswith("/api.py") and (
        name.startswith("process_") or name.endswith("_plugin") or name.startswith("build_") or name.startswith("run_")
    )


def _is_raw_llm_payload_helper(name: str) -> bool:
    return name in {"extract_json_object", "_parse_llm_response", "parse_llm_response"} or "json_object" in name


def _is_runtime_resource_probe(name: str) -> bool:
    return name in {"free_port", "find_free_port", "get_free_port", "available_port"}


def _is_live_provider_call(name: str, path: str) -> bool:
    return ("/handlers_arena.py" in path or "/arena" in path) and name.startswith(("call_", "handle_"))


def _is_generated_version_descriptor_noise(name: str, path: str) -> bool:
    if name != "describe_module":
        return False
    package = path.split("/", 1)[0]
    digits = "".join(char for char in package if char.isdigit())
    return bool(digits and (digits.endswith("00") or len(digits) >= 5))


def _domain_signal_score(name: str, path: str, groups: dict[str, tuple[str, ...]]) -> int:
    text = f"{path}:{name}"
    score = 0
    for tokens in groups.values():
        hits = [token for token in tokens if token in text]
        if hits:
            score += 10 + min(len(hits), 3) * 8
            if any(token in name for token in hits):
                score += 8
    return min(score, 46)


def level_rank(level: str) -> int:
    return {
        "core_flow": 0,
        "boundary": 1,
        "broad_split": 2,
        "preferred_anchor": 3,
        "helper_transform": 4,
    }.get(level, 9)

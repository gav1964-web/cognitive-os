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
    if is_mutation_like_first_slice_name(name):
        score -= 30
    if name.startswith("_") and level != "core_flow":
        score -= 10
    if any(token in name for token in ("handle", "process", "dispatch", "build", "create", "resolve", "validate", "parse")):
        score += 8
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
    if name in {"configure_logging", "setup_logging", "basic_config", "set_loglevel"}:
        return True
    if name in {"config", "configure", "settings"}:
        return True
    return False


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
    if "middlewares.py" in normalized_path:
        score -= 12
    if "helpers.py" in normalized_path and any(token in name for token in ("key", "name", "path", "value")):
        score -= 24
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

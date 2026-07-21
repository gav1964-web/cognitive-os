"""Ranking helpers for SpecWriter extraction contracts."""

from __future__ import annotations

from typing import Any


def name_and_contract_score(source: str, signature: dict[str, Any], side_effects: list[str]) -> tuple[int, list[str]]:
    lowered = source.lower()
    args = [str(arg.get("annotation") or "") for arg in list(signature.get("args", []) or []) if isinstance(arg, dict)]
    text = " ".join([lowered, *args]).lower()
    score = 0
    reasons: list[str] = []
    if any(token in lowered for token in ("parse_", "normalize", "validate")):
        score += 16
        reasons.append("deterministic parser/normalizer/validator shape")
    domain_score, domain_reasons = _domain_contract_score(lowered)
    score += domain_score
    reasons.extend(domain_reasons)
    representative_score, representative_reasons = _representative_slice_score(lowered)
    score += representative_score
    reasons.extend(representative_reasons)
    if _is_trivial_helper_source(lowered):
        score -= 30
        reasons.append("small helper is less representative than a flow-level capability")
    if _is_low_value_first_slice_source(lowered):
        score -= 45
        reasons.append("constructor/logging/config helper is evidence, not first implementation target")
    if _is_mutation_like_first_slice_source(lowered):
        score -= 35
        reasons.append("write/update/delete operation is side-effect evidence, not first reusable contract")
    if "memory_state" in side_effects:
        score -= 35
        reasons.append("explicit memory/global state mutation")
    if any(token in text for token in ("request", "response", "middleware", "http", "fastapi", "flask")):
        score -= 35
        reasons.append("framework request/response boundary, not first reusable core contract")
    if any(token in lowered for token in ("handler", "middleware", "endpoint")):
        score -= 20
        reasons.append("handler/middleware boundary is less reusable than a core helper")
    return score, reasons


def candidate_level_bonus(level: str) -> int:
    return {
        "core_flow": 12,
        "boundary": 8,
        "broad_split": 5,
        "preferred_anchor": 4,
        "helper_transform": 2,
    }.get(level, 0)


def operational_boundary_score(source: str, signature: dict[str, Any], claims: list[str]) -> tuple[int, list[str]]:
    lowered = source.lower()
    symbol = lowered.rsplit(":", 1)[-1]
    path = lowered.split(":", 1)[0]
    args = " ".join(str(arg.get("name") or "") for arg in list(signature.get("args", []) or []) if isinstance(arg, dict))
    text = " ".join([lowered, symbol, args, *claims]).lower()
    score = 0
    reasons: list[str] = []
    if path.endswith(("_api.py", "/api.py")) or symbol in {"request", "send", "serve", "run", "main"}:
        score -= 25
        reasons.append("API/runtime boundary should not outrank core capability candidates")
    if any(token in symbol for token in ("reload", "watch", "listen", "dispatch", "route", "emit")):
        score -= 25
        reasons.append("operational control function is less reusable as first extraction")
    if any(token in text for token in ("socket", "subprocess", "server", "event loop", "thread", "process")):
        score -= 15
        reasons.append("runtime environment coupling needs later isolation review")
    if any(token in symbol for token in ("format", "serialize", "deserialize", "encode", "decode", "canonical")):
        score += 10
        reasons.append("bounded data-shaping helper is a better extraction target")
    return score, reasons


def _domain_contract_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    score = 0
    reasons: list[str] = []
    query_symbols = {"search", "where", "filter", "matches", "evaluate", "compile_query", "parse_query"}
    if symbol in query_symbols or any(token in symbol for token in ("query", "condition", "predicate")):
        score += 28
        reasons.append("query/condition contract is a strong database first-slice target")
    if "queries.py" in path and symbol not in {"all", "any", "match"}:
        score += 18
        reasons.append("database query module is closer to reusable contract boundary")
    if symbol == "get":
        score -= 18
        reasons.append("generic accessor is weaker than query/condition contract")
    if "storages.py" in path or "/storage" in path:
        score -= 18
        reasons.append("storage adapter is persistence evidence, not first domain contract")
    if "middlewares.py" in path:
        score -= 12
        reasons.append("middleware adapter is operational evidence, not first domain contract")
    return score, reasons


def _representative_slice_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    text = f"{path}:{symbol}"
    score = 0
    reasons: list[str] = []
    flow_tokens = (
        "create_window",
        "setup_page",
        "plugin_state",
        "task_engine",
        "task_run",
        "trigger_dag",
        "process_api",
        "set_event_trigger",
        "blockwise",
        "modulegraph",
        "import_hook",
        "rebuild_archives",
        "crawler",
        "template",
    )
    utility_tokens = (
        "pixmap",
        "svg",
        "icon",
        "paint",
        "layout",
        "documentation",
        "json_schema",
        "python_type",
        "version",
        "exists",
        "helper",
    )
    if any(token in text for token in flow_tokens):
        score += 28
        reasons.append("representative domain flow/lifecycle slice")
    if any(token in text for token in utility_tokens):
        score -= 24
        reasons.append("domain utility/helper is less representative than lifecycle flow")
    if any(token in path for token in ("/plugins/", "/plugin_registration/", "/task_engine", "/blocks.py", "/modulegraph", "/archive.py")):
        score += 12
        reasons.append("source path belongs to representative domain subsystem")
    if any(token in path for token in ("/utils/", "/widgets/mixins.py", "/documentation.py")):
        score -= 12
        reasons.append("source path looks like utility/support surface")
    return score, reasons


def _is_trivial_helper_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in {"flush", "match", "storage", "no_color", "capabilities", "all", "any", "get"}:
        return True
    if any(token in symbol for token in ("cache_key", "build_key", "memcache_key", "get_path_for_link")):
        return True
    if symbol.startswith(("is_", "has_", "to_", "from_", "get_")):
        return True
    return False


def _is_low_value_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if symbol == "__init__" or path.endswith("/__init__.py"):
        return True
    if symbol in {"configure_logging", "setup_logging", "basic_config", "set_loglevel"}:
        return True
    return symbol in {"config", "configure", "settings"}


def _is_mutation_like_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in {"write", "save", "delete", "remove", "drop", "insert", "update", "commit", "flush"}:
        return True
    return symbol.startswith(("write_", "save_", "delete_", "remove_", "drop_", "insert_", "update_"))

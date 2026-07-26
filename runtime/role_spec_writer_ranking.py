"""Ranking helpers for SpecWriter extraction contracts."""

from __future__ import annotations

from typing import Any


def name_and_contract_score(source: str, signature: dict[str, Any], side_effects: list[str]) -> tuple[int, list[str]]:
    lowered = source.lower()
    args = [str(arg.get("annotation") or "") for arg in list(signature.get("args", []) or []) if isinstance(arg, dict)]
    text = " ".join([lowered, *args]).lower()
    score = 0
    reasons: list[str] = []
    if any(token in lowered for token in ("parse_", "normalize", "validate", "resolve", "build_", "make_", "create_")):
        score += 16
        reasons.append("deterministic parser/normalizer/validator shape")
    domain_score, domain_reasons = _domain_contract_score(lowered)
    score += domain_score
    reasons.extend(domain_reasons)
    repair_score, repair_reasons = _repair_loop_contract_score(lowered)
    score += repair_score
    reasons.extend(repair_reasons)
    representative_score, representative_reasons = _representative_slice_score(lowered)
    score += representative_score
    reasons.extend(representative_reasons)
    if _is_trivial_helper_source(lowered):
        score -= 30
        reasons.append("small helper is less representative than a flow-level capability")
    if _is_liveness_probe_source(lowered):
        score -= 35
        reasons.append("health/status/ping probe is liveness evidence, not first reusable domain contract")
    if _is_bootstrap_support_source(lowered):
        score -= 55
        reasons.append("CLI/bootstrap support helper is evidence, not first architectural slice")
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


def _repair_loop_contract_score(lowered_source: str) -> tuple[int, list[str]]:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    text = f"{path}:{symbol}"
    score = 0
    reasons: list[str] = []
    if any(token in text for token in ("auto_dev_agent.py", "module_contract_checker.py", "goal_to_spec.py", "run_all_autofix.py")):
        score += 18
        reasons.append("source belongs to LLM auto-repair control surface")
    if symbol in {"send_to_model", "extract_json_from_model_response"}:
        score += 44
        reasons.append("LLM hypothesis boundary is central to repair-attempt contract")
    if symbol in {"check_single_module_output", "clean_module_output"}:
        score += 38
        reasons.append("module contract checker is a strong validation boundary")
    if symbol == "goal_to_spec":
        score += 30
        reasons.append("goal-to-spec transform is a useful planning contract boundary")
    if symbol in {"fix_module_until_success", "regenerate_module"}:
        score += 22
        reasons.append("repair orchestration loop is representative but needs bounded subcontracts")
    if "generated_v" in path or "/generated" in path:
        score -= 70
        reasons.append("generated project output is evidence, not first source transformation target")
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
    if symbol in {"handle_request", "handle_async_request"}:
        score -= 40
        reasons.append("request dispatcher boundary is evidence, not first reusable core contract")
    if any(token in symbol for token in ("reload", "watch", "listen", "dispatch", "route", "emit")):
        score -= 25
        reasons.append("operational control function is less reusable as first extraction")
    if symbol in {"run", "setup", "install", "cancel", "decorator"} or symbol.endswith(("_ctx", "_context")):
        score -= 30
        reasons.append("operational lifecycle/mutation wrapper needs a narrower contract target")
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
    query_symbols = {"search", "where", "filter", "matches", "compile_query", "parse_query"}
    query_path = any(token in path for token in ("query", "queries.py", "table.py", "database", "db/"))
    if symbol in query_symbols or (query_path and symbol == "evaluate") or any(token in symbol for token in ("query", "condition", "predicate")):
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
        "run_consensus",
        "orchestrator",
        "group_manager",
        "a2a_protocol",
        "agent",
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
    if _is_ml_inference_source(path, symbol):
        score += 36
        reasons.append("ML inference/submission boundary is representative for competition workflow")
    if _is_protocol_event_boundary(path, symbol):
        score += 32
        reasons.append("protocol event/state-machine boundary is representative")
    if _is_connection_lifecycle_boundary(path, symbol):
        score += 30
        reasons.append("connection/proxy lifecycle boundary is representative")
    if _is_markup_escape_boundary(path, symbol):
        score += 48
        reasons.append("markup escaping/sanitization boundary is project-core behavior")
    if symbol == "evaluate" and any(token in path for token in ("x31.py", "notebook", "competition")):
        score -= 30
        reasons.append("ad-hoc evaluator is less stable than generation/postprocessing contract")
    return score, reasons


def _is_ml_inference_source(path: str, symbol: str) -> bool:
    if symbol in {"generate_response", "postprocess", "build_submission_row", "write_submission"}:
        return True
    return any(token in path for token in ("inference", "submission", "predict")) and symbol in {"generate", "predict", "postprocess"}


def _is_trivial_helper_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in {
        "capitalize",
        "casefold",
        "center",
        "count",
        "endswith",
        "find",
        "flush",
        "format",
        "get",
        "index",
        "join",
        "lower",
        "lstrip",
        "match",
        "removeprefix",
        "removesuffix",
        "replace",
        "rstrip",
        "split",
        "startswith",
        "storage",
        "strip",
        "title",
        "upper",
        "no_color",
        "capabilities",
        "all",
        "any",
    }:
        return True
    if any(token in symbol for token in ("cache_key", "build_key", "memcache_key", "get_path_for_link")):
        return True
    if symbol.endswith(("_path", "_url", "_name", "_version")) and not any(
        token in symbol for token in ("parse", "build", "resolve", "normalize", "validate")
    ):
        return True
    if symbol.startswith(("is_", "has_", "to_", "from_", "get_")):
        return True
    return False


def _is_liveness_probe_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    return symbol in {"health", "healthcheck", "status", "ping", "ready", "readiness", "live", "liveness"}


def _is_bootstrap_support_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if symbol in {"parse_args", "main", "is_ignored", "should_ignore", "ignored", "setup", "configure"}:
        return True
    if symbol.endswith("_args") and any(token in path for token in ("cli", "main.py", "prompt_lab.py", "map.py")):
        return True
    return False


def _is_protocol_event_boundary(path: str, symbol: str) -> bool:
    if symbol in {"next_event", "send", "receive_data", "process_input"}:
        return any(token in path for token in ("connection", "protocol", "state", "events"))
    return False


def _is_connection_lifecycle_boundary(path: str, symbol: str) -> bool:
    if symbol.startswith(("_init_", "init_")) and "connection" in symbol:
        return any(token in path for token in ("connection", "proxy", "transport", "network"))
    if symbol in {"create_connection", "connect_tcp", "connect_unix_socket", "start_tls"}:
        return True
    return False


def _is_markup_escape_boundary(path: str, symbol: str) -> bool:
    if symbol in {"escape", "escape_silent", "striptags", "_escape_inner"}:
        return any(token in path for token in ("markupsafe", "markup", "escape"))
    return False


def _is_low_value_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    path = lowered_source.split(":", 1)[0]
    if symbol == "__init__" or path.endswith("/__init__.py"):
        return True
    if symbol in {"configure_logging", "setup_logging", "basic_config", "set_loglevel"}:
        return True
    return symbol in {"config", "configure", "settings", "setup", "decorator"}


def _is_mutation_like_first_slice_source(lowered_source: str) -> bool:
    symbol = lowered_source.rsplit(":", 1)[-1]
    if symbol in {"write", "save", "delete", "remove", "drop", "insert", "update", "commit", "flush", "install", "cancel"}:
        return True
    return symbol.startswith(("write_", "save_", "delete_", "remove_", "drop_", "insert_", "update_", "install_", "cancel_"))

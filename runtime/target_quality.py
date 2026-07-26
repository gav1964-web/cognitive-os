"""Quality heuristics for selected first-slice targets."""

from __future__ import annotations

from typing import Any


SUSPICIOUS_PATH_TOKENS = (
    "/tests/",
    "/test/",
    "/docs/",
    "/examples/",
    "/scripts/",
    "/tools/",
    "/utils/",
    "/helpers",
    "documentation.py",
    "runtests.py",
    "hatch_build.py",
    "install_dev_repos.py",
)

SUSPICIOUS_SYMBOL_TOKENS = (
    "add_ctx",
    "cancel",
    "decorator",
    "exists",
    "install",
    "version",
    "pixmap",
    "icon",
    "paint",
    "layout",
    "json_schema",
    "python_type",
    "helper",
)

REPRESENTATIVE_TOKENS = (
    "archive",
    "blockwise",
    "crawler",
    "dag",
    "event_trigger",
    "flow",
    "import_hook",
    "modulegraph",
    "plugin_state",
    "process_api",
    "rebuild",
    "task_engine",
    "task_run",
    "template",
    "trigger",
)


STRONG_CONTRACT_TOKENS = (
    "build_providers_from_config",
    "calculate",
    "compile",
    "decode",
    "deserialize",
    "encode",
    "format",
    "escape",
    "load_payload",
    "normalize",
    "parse",
    "resolve",
    "search",
    "serialize",
    "sign",
    "unsign",
    "validate",
)

STRONG_CONTRACT_PREFIXES = (
    "build_",
    "create_",
    "make_",
    "query_",
)

STRONG_CONTRACT_SYMBOLS = (
    "create",
)

META_INFRASTRUCTURE_TOKENS = (
    "_capability_acquisition",
    "acquire_capability",
    "capability_registry",
    "foundry",
    "prompt",
    "semantic",
)

RUNTIME_BOUNDARY_TOKENS = (
    "handle_async_request",
    "handle_request",
    "middleware",
    "proxy_to",
    "provider_url",
    "request",
    "response",
    "route",
    "run",
)


def semantic_target_quality_report(
    target: str,
    *,
    ranked_candidates: list[str] | None = None,
    source_evidence: list[str] | None = None,
    selection_reason: str = "",
) -> dict[str, Any]:
    if not target:
        return {"status": "blocked", "target": "", "score": 0, "reasons": ["no selected extraction candidate"]}
    ranked_candidates = ranked_candidates or []
    source_evidence = source_evidence or []
    lowered = target.replace("\\", "/").lower()
    symbol = lowered.rsplit(":", 1)[-1]
    path = lowered.split(":", 1)[0]
    reason_text = selection_reason.lower()
    score = 60
    reasons = ["selected extraction candidate exists"]

    if ranked_candidates and ranked_candidates[0] == target:
        score += 8
        reasons.append("candidate is ranked first by SpecWriter")
    if target in source_evidence:
        score += 8
        reasons.append("candidate is present in source evidence")
    if _strong_contract_hit(lowered, symbol):
        score += 18
        reasons.append("candidate name suggests a bounded contract")
    if any(token in lowered for token in REPRESENTATIVE_TOKENS):
        score += 16
        reasons.append("representative domain target / lifecycle target")
    if _protocol_event_boundary(path, symbol):
        score += 16
        reasons.append("protocol event/state-machine target")
    if _connection_lifecycle_boundary(path, symbol):
        score += 18
        reasons.append("connection/proxy lifecycle target")
    if _exception_formatting_boundary(path, symbol):
        score += 8
        reasons.append("exception formatting/reporting target")
    if _signed_token_boundary(path, symbol):
        score += 8
        reasons.append("signed-token verification boundary")
    if _markup_escape_boundary(path, symbol):
        score += 18
        reasons.append("markup escaping/sanitization target")
    if _provider_capability_boundary(symbol):
        score += 18
        reasons.append("provider capability listing is a bounded integration contract")
    if _mock_assertion_boundary(path, symbol):
        score += 18
        reasons.append("mock assertion wrapper is a bounded testing-plugin contract")
    if "pure transform" in reason_text or "deterministic parser" in reason_text:
        score += 8
        reasons.append("ranking reason marks deterministic transform")
    repair_boundary = "llm hypothesis boundary" in reason_text or "repair-attempt contract" in reason_text
    if repair_boundary and "send_to_model" in lowered:
        score += 18
        reasons.append("LLM repair hypothesis boundary is a valid architectural contract target")
    ml_generation_boundary = "ml inference/submission boundary" in reason_text or "ml generation" in reason_text
    if ml_generation_boundary and "generate_response" in lowered:
        score += 18
        reasons.append("ML generation boundary is a valid architectural contract target")
    prompt_lab_boundary = "prompt_lab" in lowered and (
        "first-slice target" in reason_text or "prompt-lab" in reason_text or "run artifact" in reason_text
    )
    if prompt_lab_boundary:
        score += 18
        reasons.append("prompt-lab run/artifact boundary is a valid project-domain target")

    suspicious = _suspicious_hits(path, symbol)
    meta = [token for token in META_INFRASTRUCTURE_TOKENS if token in lowered]
    boundary = _runtime_boundary_hits(lowered, symbol)
    trivial = _trivial_symbol(symbol)
    bootstrap = _bootstrap_support_symbol(path, symbol)
    if suspicious:
        score -= min(30, 10 + len(suspicious) * 5)
        reasons.append("support/utility target: " + ", ".join(suspicious[:4]))
    if meta and not prompt_lab_boundary:
        score -= min(45, 20 + len(meta) * 8)
        reasons.append("meta-infrastructure target, not project-domain slice: " + ", ".join(meta[:4]))
    if boundary and not (repair_boundary or ml_generation_boundary):
        score -= min(35, 12 + len(boundary) * 5)
        reasons.append("runtime/API boundary target needs semantic review: " + ", ".join(boundary[:4]))
    if trivial:
        score -= 25
        reasons.append("trivial accessor/value helper is weak as first architectural slice")
    if _liveness_probe_symbol(symbol):
        score -= 35
        reasons.append("health/status/ping probe is weak as first architectural slice")
    if bootstrap:
        score -= 45
        reasons.append("CLI/bootstrap support helper is weak as first architectural slice")

    score = max(0, min(100, score))
    disqualifying_boundary = boundary and not (repair_boundary or ml_generation_boundary)
    disqualifying_meta = meta and not prompt_lab_boundary
    liveness_probe = _liveness_probe_symbol(symbol)
    if score >= 85 and not (suspicious or disqualifying_meta or disqualifying_boundary or trivial or bootstrap or liveness_probe):
        status = "strong"
    elif score >= 65 and not (disqualifying_meta or trivial or bootstrap or liveness_probe):
        status = "acceptable"
    elif score >= 40:
        status = "suspicious"
    else:
        status = "poor"
    return {"status": status, "target": target, "score": score, "reasons": reasons}


def target_quality_report(role_quality: dict[str, Any]) -> dict[str, Any]:
    target = str(role_quality.get("selected_extraction_candidate") or "")
    if not target:
        return {
            "status": "blocked",
            "target": "",
            "score": 0,
            "reasons": ["no selected extraction candidate"],
        }
    semantic = semantic_target_quality_report(target)
    lowered = target.replace("\\", "/").lower()
    score = int(semantic["score"])
    reasons = list(semantic["reasons"])
    if role_quality.get("implementation_binding_status") == "bound_to_extraction_contract":
        score += 10
        reasons.append("implementation is bound to extraction contract")
    if role_quality.get("test_has_contract_matrix"):
        score += 10
        reasons.append("contract test matrix present")
    if role_quality.get("test_has_negative_tests_for_target"):
        score += 10
        reasons.append("negative tests cover target")
    suspicious = [token for token in SUSPICIOUS_PATH_TOKENS + SUSPICIOUS_SYMBOL_TOKENS if token in lowered]
    if suspicious:
        score -= min(45, 15 + len(suspicious) * 6)
        reasons.append("suspicious utility/support target: " + ", ".join(suspicious[:4]))
    status = "good" if score >= 85 and not suspicious else "suspicious" if score >= 50 else "poor"
    return {
        "status": status,
        "target": target,
        "score": max(0, min(100, score)),
        "reasons": reasons,
    }


def _runtime_boundary_hits(lowered: str, symbol: str) -> list[str]:
    hits = []
    for token in RUNTIME_BOUNDARY_TOKENS:
        if token in {"request", "response", "route", "run"}:
            if token == symbol or symbol.startswith(f"{token}_") or symbol.endswith(f"_{token}") or f"_{token}_" in symbol:
                hits.append(token)
            continue
        if token in lowered:
            hits.append(token)
    return hits


def _strong_contract_hit(lowered: str, symbol: str) -> bool:
    normalized_symbol = symbol.lstrip("_")
    if normalized_symbol in STRONG_CONTRACT_SYMBOLS:
        return True
    if normalized_symbol.startswith(STRONG_CONTRACT_PREFIXES):
        return True
    return any(token in lowered for token in STRONG_CONTRACT_TOKENS)


def _trivial_symbol(symbol: str) -> bool:
    if symbol in {
        "capitalize",
        "casefold",
        "center",
        "config",
        "count",
        "endswith",
        "exists",
        "find",
        "get",
        "has",
        "index",
        "is",
        "join",
        "lower",
        "lstrip",
        "provider_url",
        "removeprefix",
        "removesuffix",
        "replace",
        "rstrip",
        "settings",
        "split",
        "startswith",
        "strip",
        "title",
        "upper",
        "version",
    }:
        return True
    if symbol.startswith(("get_", "has_", "is_", "to_", "from_")):
        return True
    if symbol.endswith(("_url", "_path", "_name", "_version")) and not any(
        token in symbol for token in ("parse", "build", "resolve", "normalize")
    ):
        return True
    return False


def _liveness_probe_symbol(symbol: str) -> bool:
    return symbol in {"health", "healthcheck", "status", "ping", "ready", "readiness", "live", "liveness"}


def _provider_capability_boundary(symbol: str) -> bool:
    return symbol in {"list_provider_capabilities", "provider_capabilities", "describe_provider_capabilities"}


def _mock_assertion_boundary(path: str, symbol: str) -> bool:
    return "pytest_mock" in path and symbol in {
        "assert_has_calls_wrapper",
        "assert_wrapper",
        "wrap_assert_methods",
        "unwrap_assert_methods",
    }


def _bootstrap_support_symbol(path: str, symbol: str) -> bool:
    if symbol in {"parse_args", "main", "is_ignored", "should_ignore", "ignored", "setup", "configure"}:
        return True
    if symbol.endswith("_args") and any(token in path for token in ("cli", "main.py", "prompt_lab.py", "map.py")):
        return True
    return False


def _suspicious_hits(path: str, symbol: str) -> list[str]:
    hits = [token for token in SUSPICIOUS_PATH_TOKENS if token in path]
    hits.extend(token for token in SUSPICIOUS_SYMBOL_TOKENS if token in symbol)
    path_parts = {part for part in path.replace("\\", "/").split("/") if part}
    if ("icons" in path_parts or "icon" in path_parts) and "icon" not in hits:
        hits.append("icon")
    return hits


def _protocol_event_boundary(path: str, symbol: str) -> bool:
    if symbol in {"next_event", "send", "receive_data", "process_input"}:
        return any(token in path for token in ("connection", "protocol", "state", "events"))
    return False


def _connection_lifecycle_boundary(path: str, symbol: str) -> bool:
    if symbol.startswith(("_init_", "init_")) and "connection" in symbol:
        return any(token in path for token in ("connection", "proxy", "transport", "network"))
    if symbol in {"create_connection", "connect_tcp", "connect_unix_socket", "start_tls"}:
        return True
    return False


def _markup_escape_boundary(path: str, symbol: str) -> bool:
    if symbol in {"escape", "escape_silent", "striptags", "_escape_inner"}:
        return any(token in path for token in ("markupsafe", "markup", "escape"))
    return False


def _exception_formatting_boundary(path: str, symbol: str) -> bool:
    return "exception" in symbol and any(token in symbol for token in ("format", "render", "serialize")) and any(
        token in path for token in ("traceback", "_code", "exception")
    )


def _signed_token_boundary(path: str, symbol: str) -> bool:
    if symbol in {"sign", "unsign", "verify_signature", "derive_key"}:
        return any(token in path for token in ("itsdangerous", "signer", "serializer", "token", "security"))
    return False

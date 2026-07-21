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
    "exists",
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


def target_quality_report(role_quality: dict[str, Any]) -> dict[str, Any]:
    target = str(role_quality.get("selected_extraction_candidate") or "")
    if not target:
        return {
            "status": "blocked",
            "target": "",
            "score": 0,
            "reasons": ["no selected extraction candidate"],
        }
    lowered = target.replace("\\", "/").lower()
    score = 70
    reasons = ["selected extraction candidate exists"]
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
    representative = [token for token in REPRESENTATIVE_TOKENS if token in lowered]
    if representative:
        score += min(20, 8 + len(representative) * 4)
        reasons.append("representative domain target: " + ", ".join(representative[:4]))
    status = "good" if score >= 85 and not suspicious else "suspicious" if score >= 50 else "poor"
    return {
        "status": status,
        "target": target,
        "score": max(0, min(100, score)),
        "reasons": reasons,
    }

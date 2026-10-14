"""Domain flow anchor detection for large Python projects."""

from __future__ import annotations

from typing import Any

from .path_priority import path_priority


def domain_flow_anchors(functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in functions:
        path = str(item.get("path", ""))
        name = str(item.get("name", ""))
        score = domain_anchor_score(path, name, item)
        if score <= 0:
            continue
        rows.append(
            {
                "path": item.get("path"),
                "name": item.get("name"),
                "line": item.get("line"),
                "loc": item.get("loc"),
                "call_count": len(item.get("calls", [])),
                "side_effects": item.get("side_effects", []),
                "domain_anchor_score": score,
            }
        )
    return sorted(rows, key=lambda item: (-int(item["domain_anchor_score"]), path_priority(str(item.get("path", ""))), str(item.get("path", ""))))[:16]


def domain_anchor_score(path: str, name: str, item: dict[str, Any]) -> int:
    text = f"{path}:{name}".replace("\\", "/").lower()
    if any(token in text for token in ("/tests/", "/docs/", "external-deps", "waflib", "runtests.py", "hatch_build.py", "documentation.py")):
        return 0
    groups = (
        ("dag", "flow", "task", "scheduler", "trigger", "state", "worker"),
        ("playbook", "inventory", "module", "template", "connection", "execute"),
        ("archive", "repository", "manifest", "chunk", "restore", "backup"),
        ("analysis", "hook", "spec", "bundle", "bootloader", "modulegraph"),
        ("proxy", "flow", "cert", "tls", "intercept", "websocket"),
        ("plugin", "widget", "editor", "lsp", "workspace", "preferences"),
        ("component", "blocks", "interface", "queue", "api", "predict"),
        ("graph", "blockwise", "scheduler", "array", "dataframe", "partition"),
    )
    hits = [token for tokens in groups for token in tokens if token in text]
    if not hits:
        return 0
    score = 30 + min(len(set(hits)), 5) * 8
    score += min(int(item.get("loc") or 0), 160) // 20
    score += min(len(item.get("calls", [])), 20)
    if any(token in name for token in ("run", "trigger", "execute", "schedule", "dispatch", "process")):
        score += 18
    if name.startswith(("build_", "make_", "create_")) and any(token in text for token in ("task", "state", "config")):
        score -= 10
    if item.get("side_effects"):
        score -= 8
    if name.startswith(("get_", "is_", "has_", "to_", "from_")):
        score -= 20
    return score

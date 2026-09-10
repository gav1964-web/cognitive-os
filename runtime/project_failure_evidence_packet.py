"""Build a bounded source-backed packet for one project-native failure."""

from __future__ import annotations

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .project_development_source_targets import resolve_python_target


REQUIRED_FAILURE_EVIDENCE_CHECKS = (
    "stable_failure_signature",
    "exact_target_is_source_backed",
    "failing_test_source_is_present",
    "observed_failure_is_detailed",
)


def evidence_packet_digest(packet: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in packet.items() if key != "packet_digest"}
    return _digest(unsigned)


def is_complete_failure_evidence_packet(
    packet: dict[str, Any], *, target: str,
) -> bool:
    checks = dict(packet.get("checks") or {})
    reproduction = dict(packet.get("reproduction") or {})
    return bool(
        packet.get("artifact_type") == "ProjectFailureEvidencePacket"
        and packet.get("schema_version") == "project_failure_evidence_packet.v1"
        and packet.get("status") == "complete"
        and packet.get("target") == target
        and packet.get("execution_authorized") is False
        and all(checks.get(name) is True for name in REQUIRED_FAILURE_EVIDENCE_CHECKS)
        and packet.get("failure_signature")
        and dict(packet.get("target_source") or {})
        and list(packet.get("test_sources") or [])
        and _detailed_failure(str(packet.get("observed_failure") or ""))
        and reproduction.get("stable_signature") is True
        and int(reproduction.get("matching_repetitions") or 0) >= 2
        and packet.get("packet_digest") == evidence_packet_digest(packet)
    )


def attach_failure_evidence_packets(
    diagnosis: dict[str, Any], *, project_dir: Path,
    chain_case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = deepcopy(diagnosis)
    for issue in result.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        rows = [row for row in issue.get("failure_evidence") or [] if isinstance(row, dict)]
        packets = [
            build_failure_evidence_packet(
                project_dir=project_dir, failure=dict(row), chain_case=chain_case
            )
            for row in rows
        ]
        if packets:
            issue["failure_evidence_packets"] = packets
            if len(packets) == 1:
                issue["failure_evidence_packet"] = packets[0]
    return result


def build_failure_evidence_packet(
    *, project_dir: Path, failure: dict[str, Any],
    chain_case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = str(failure.get("target") or "")
    signature = str(failure.get("failure_signature") or "")
    target_source = _target_source(project_dir, target)
    tests = [
        item for nodeid in _strings(failure.get("failing_nodeids"))[:8]
        if (item := _test_source(project_dir, nodeid)) is not None
    ]
    repetitions = _matching_repetitions(chain_case, signature, target)
    output = _best_output(repetitions, failure)
    checks = dict.fromkeys(REQUIRED_FAILURE_EVIDENCE_CHECKS, False)
    checks.update({
        "stable_failure_signature": bool(signature) and len(repetitions) >= 2,
        "exact_target_is_source_backed": bool(target_source),
        "failing_test_source_is_present": bool(tests),
        "observed_failure_is_detailed": _detailed_failure(output),
    })
    body = {
        "artifact_type": "ProjectFailureEvidencePacket",
        "schema_version": "project_failure_evidence_packet.v1",
        "status": "complete" if all(checks.values()) else "partial",
        "target": target,
        "failure_signature": signature,
        "failure_kind": failure.get("failure_kind"),
        "failing_nodeids": _strings(failure.get("failing_nodeids"))[:8],
        "observed_failure": output[:6000],
        "assertion_evidence": _assertion_lines(output),
        "target_source": target_source,
        "test_sources": tests,
        "reproduction": {
            "matching_repetitions": len(repetitions),
            "exit_codes": [row.get("exit_code") for row in repetitions[:8]],
            "stable_signature": bool(signature) and len(repetitions) >= 2,
        },
        "checks": checks,
        "execution_authorized": False,
        "source_changes": False,
    }
    body["packet_digest"] = evidence_packet_digest(body)
    return body


def _target_source(project_dir: Path, target: str) -> dict[str, Any] | None:
    resolved = resolve_python_target(project_dir, target)
    path = resolved.get("path")
    if not isinstance(path, Path):
        return None
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError):
        return None
    symbol = str(resolved.get("symbol") or "")
    nodes = _qualified_functions(tree, symbol)
    if len(nodes) != 1:
        return None
    excerpt = ast.get_source_segment(text, nodes[0]) or ""
    if not excerpt:
        return None
    return {
        "path": str(resolved.get("relative_path") or ""),
        "symbol": symbol,
        "line_start": nodes[0].lineno,
        "line_end": getattr(nodes[0], "end_lineno", nodes[0].lineno),
        "excerpt": excerpt[:8000],
        "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def _test_source(project_dir: Path, nodeid: str) -> dict[str, Any] | None:
    path_text, _, selector = nodeid.partition("::")
    root = project_dir.resolve()
    path = (root / path_text).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file() or path.suffix.lower() != ".py":
        return None
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError):
        return None
    leaf = selector.split("::")[-1].split("[", 1)[0]
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == leaf
    ]
    excerpt = ast.get_source_segment(text, matches[0]) if len(matches) == 1 else text[:5000]
    excerpt = excerpt or ""
    return {
        "nodeid": nodeid,
        "path": path.relative_to(root).as_posix(),
        "excerpt": excerpt[:5000],
        "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }


def _qualified_functions(tree: ast.Module, symbol: str) -> list[ast.AST]:
    parts = symbol.split(".")
    if len(parts) == 1:
        return [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[0]
        ]
    if len(parts) != 2:
        return []
    owners = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
    return [
        node for owner in owners for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[1]
    ]


def _matching_repetitions(
    chain_case: dict[str, Any] | None, signature: str, target: str,
) -> list[dict[str, Any]]:
    rows = []
    for row in dict(chain_case or {}).get("repetitions") or []:
        if not isinstance(row, dict):
            continue
        same_signature = not signature or str(row.get("failure_signature") or "") == signature
        production = _strings(row.get("production_targets"))
        same_target = not target or row.get("leaf_production_target") == target or target in production
        if same_signature and same_target:
            rows.append(dict(row))
    return rows


def _best_output(repetitions: list[dict[str, Any]], failure: dict[str, Any]) -> str:
    outputs = [str(row.get("output_tail") or "") for row in repetitions]
    outputs.extend([
        str(failure.get("output_tail") or ""),
        str(failure.get("detail") or ""),
    ])
    return max((value for value in outputs if value), key=len, default="")


def _assertion_lines(output: str) -> list[str]:
    markers = ("assert ", "E   ", "FAILED ", "Error:", "Exception:")
    return [line.strip()[:500] for line in output.splitlines() if any(marker in line for marker in markers)][:24]


def _detailed_failure(output: str) -> bool:
    lower = output.lower()
    return len(output.strip()) >= 40 and any(marker in lower for marker in ("assert", "error", "exception", "failed "))


def _strings(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)):
        return [str(value)] if value else []
    return [str(item) for item in value or [] if item]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

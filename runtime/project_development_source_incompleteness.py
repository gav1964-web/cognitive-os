"""Source incompleteness scanner for project-development planning."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path
from typing import Any

from .python_source_files import iter_python_source_files


_FAILURE_AUTHORITIES = {
    "failing_contract_test",
    "executable_acceptance_failure",
    "explicit_user_failure",
}


def collect_source_incompleteness_evidence(
    project_dir: Path,
    *,
    corroborating_failures: list[dict[str, Any]] | None = None,
    maximum_files: int = 500,
    maximum_findings: int = 80,
) -> dict[str, Any]:
    """Classify stub-like syntax without treating syntax alone as a defect."""
    root = project_dir.resolve()
    failures = _failure_index(corroborating_failures or [])
    findings: list[dict[str, Any]] = []
    files_scanned = 0
    parse_failures = 0
    truncated = False
    for path in iter_python_source_files(root):
        if _is_nonproduction_source(path, root):
            continue
        if files_scanned >= maximum_files:
            truncated = True
            break
        files_scanned += 1
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            parse_failures += 1
            continue
        relative = path.relative_to(root).as_posix()
        comments = _comment_tokens(source)
        findings.extend(_stub_findings(tree, relative, comments, failures))
        findings.extend(_exception_suppression_findings(tree, relative, comments))
        if len(findings) >= maximum_findings:
            findings = findings[:maximum_findings]
            truncated = True
            break
    actionable = [row for row in findings if row["actionable"]]
    return {
        "artifact_type": "SourceIncompletenessEvidence",
        "status": "actionable" if actionable else "observations_only",
        "files_scanned": files_scanned,
        "parse_failures": parse_failures,
        "truncated": truncated,
        "finding_count": len(findings),
        "actionable_count": len(actionable),
        "findings": findings,
        "actionable_findings": actionable,
        "interpretation_policy": (
            "stub syntax and intent comments are observations; an executable or user failure "
            "bound to the same target is required for action"
        ),
    }


def _failure_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target") or "").replace("\\", "/")
        authority = str(row.get("authority") or "")
        if target and authority in _FAILURE_AUTHORITIES:
            result[target] = {
                "authority": authority,
                "detail": str(row.get("detail") or ""),
            }
    return result


def _is_nonproduction_source(path: Path, root: Path) -> bool:
    parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
    return bool(parts.intersection({"test", "tests", "testing", "fixtures", "examples"}))


def _comment_tokens(source: str) -> dict[int, str]:
    comments = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string.lstrip("#").strip()
    except (IndentationError, tokenize.TokenError):
        return comments
    return comments


def _stub_findings(
    tree: ast.Module,
    path: str,
    comments: dict[int, str],
    failures: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    findings = []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stub_kind = _stub_kind(node)
        if stub_kind is None:
            continue
        parent_class = _parent_class(node, parents)
        target_name = node.name if parent_class is None else f"{parent_class.name}.{node.name}"
        target = f"{path}:{target_name}"
        marker = _nearby_intent_comment(node, comments)
        classification = _stub_classification(node, parent_class, marker)
        failure = failures.get(target)
        if failure is not None:
            classification = "corroborated_incomplete"
        findings.append({
            "target": target,
            "line": int(node.lineno),
            "signal": stub_kind,
            "classification": classification,
            "intent_marker": marker,
            "actionable": failure is not None,
            "authority": failure.get("authority") if failure else None,
            "detail": failure.get("detail") if failure else None,
        })
    return findings


def _exception_suppression_findings(
    tree: ast.Module, path: str, comments: dict[int, str]
) -> list[dict[str, Any]]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _body_is_stub(node.body, allow_docstring=False):
            continue
        findings.append({
            "target": f"{path}:except@{node.lineno}",
            "line": int(node.lineno),
            "signal": "pass",
            "classification": "intentional_exception_suppression",
            "intent_marker": _nearby_comment_lines(node.lineno, getattr(node, "end_lineno", node.lineno), comments),
            "actionable": False,
            "authority": None,
            "detail": None,
        })
    return findings


def _stub_kind(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1:
        return None
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return "pass"
    if isinstance(statement, ast.Raise) and _is_not_implemented(statement.exc):
        return "raise_not_implemented"
    return None


def _body_is_stub(body: list[ast.stmt], *, allow_docstring: bool) -> bool:
    rows = list(body)
    if allow_docstring and rows and isinstance(rows[0], ast.Expr) and isinstance(rows[0].value, ast.Constant) and isinstance(rows[0].value.value, str):
        rows = rows[1:]
    return len(rows) == 1 and isinstance(rows[0], ast.Pass)


def _is_not_implemented(node: ast.expr | None) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"NotImplemented", "NotImplementedError"}
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "NotImplementedError"
    )


def _parent_class(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.ClassDef | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current
        current = parents.get(current)
    return None


def _stub_classification(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    parent_class: ast.ClassDef | None,
    marker: str | None,
) -> str:
    if isinstance(node, ast.ClassDef):
        lowered = node.name.lower()
        if lowered.endswith(("error", "exception")):
            return "intentional_marker_type"
        return "declared_future_work" if marker else "ambiguous_placeholder_type"
    decorators = {_decorator_name(row) for row in node.decorator_list}
    class_bases = {_decorator_name(row) for row in (parent_class.bases if parent_class else [])}
    if "abstractmethod" in decorators or class_bases.intersection({"ABC", "Protocol"}) or node.name.startswith("__"):
        return "intentional_interface_boundary"
    return "declared_future_work" if marker else "ambiguous_stub"


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _nearby_intent_comment(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    comments: dict[int, str],
) -> str | None:
    marker = _nearby_comment_lines(max(1, node.lineno - 1), min(getattr(node, "end_lineno", node.lineno), node.lineno + 4), comments)
    if marker and any(token in marker.lower() for token in ("todo", "fixme", "not implemented", "implement", "add ")):
        return marker
    return None


def _nearby_comment_lines(start: int, end: int, comments: dict[int, str]) -> str | None:
    values = [comments[line] for line in range(start, end + 1) if comments.get(line)]
    return " | ".join(values) if values else None

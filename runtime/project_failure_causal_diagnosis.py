"""Training-only causal hypotheses for repeated project-native failures."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


KNOWLEDGE_PATH = Path("knowledge/role_knowledge/project_failure_causal_hypotheses.json")


def enrich_failure_diagnosis(
    diagnosis: dict[str, Any], *, project_dir: Path, workspace_root: Path
) -> dict[str, Any]:
    row = deepcopy(diagnosis)
    for issue in row.get("issues") or []:
        if not isinstance(issue, dict) or issue.get("failure_specific_reducer_required") is not True:
            continue
        hypothesis = infer_causal_hypothesis(
            issue, project_dir=project_dir, workspace_root=workspace_root
        )
        if not hypothesis:
            continue
        issue["causal_hypothesis"] = hypothesis["causal_hypothesis"]
        issue["repair_design"] = hypothesis["repair_design"]
        issue["proposed_operator_ids"] = [hypothesis["repair_design"]["proposed_operator_id"]]
    return row


def infer_causal_hypothesis(
    issue: dict[str, Any], *, project_dir: Path, workspace_root: Path
) -> dict[str, Any] | None:
    targets = [str(value) for value in issue.get("affected_targets") or [] if value]
    failures = [dict(value) for value in issue.get("failure_evidence") or [] if isinstance(value, dict)]
    if len(targets) != 1 or not failures:
        return None
    source = _target_source(project_dir, targets[0])
    if not source:
        return None
    failure_text = "\n".join([
        str(failures[0].get("detail") or ""),
        *[str(value) for value in failures[0].get("failing_nodeids") or []],
    ]).lower()
    for pattern in _load_knowledge(workspace_root).get("patterns") or []:
        if not isinstance(pattern, dict) or not _matches(pattern, failure_text, source.lower()):
            continue
        evidence = [
            f"failure_signature:{failures[0].get('failure_signature')}",
            f"target_source:{targets[0]}",
            f"training_pattern:{pattern.get('id')}",
        ]
        return {
            "causal_hypothesis": {
                "status": "training_hypothesis",
                "pattern_id": pattern.get("id"),
                "mechanism": pattern.get("mechanism"),
                "evidence": evidence,
                "execution_authority": False,
            },
            "repair_design": {
                "status": "proposal_review_required",
                "target": targets[0],
                "mechanism": pattern.get("repair_mechanism"),
                "mutation_contract": pattern.get("mutation_contract"),
                "proposed_operator_id": pattern.get("proposed_operator_id"),
                "evidence": evidence,
                "execution_authority": False,
            },
        }
    return None


def _target_source(project_dir: Path, target: str) -> str:
    path_text, _, symbol = target.partition(":")
    path = project_dir / path_text
    if not path.is_file() or path.suffix.lower() != ".py":
        return ""
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, UnicodeError, SyntaxError):
        return ""
    leaf = symbol.rsplit(".", 1)[-1]
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == leaf
    ]
    return ast.get_source_segment(text, candidates[0]) or "" if len(candidates) == 1 else ""


def _matches(pattern: dict[str, Any], failure_text: str, source_text: str) -> bool:
    failures = [str(value).lower() for value in pattern.get("required_failure_contains_all") or []]
    sources = [str(value).lower() for value in pattern.get("required_source_contains_all") or []]
    return bool(failures and sources) and all(value in failure_text for value in failures) and all(
        value in source_text for value in sources
    )


def _load_knowledge(workspace_root: Path) -> dict[str, Any]:
    payload = json.loads((workspace_root / KNOWLEDGE_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_failure_causal_hypotheses.v1":
        raise ValueError("invalid project failure causal hypothesis knowledge")
    if payload.get("status") != "training_only":
        raise ValueError("causal hypothesis knowledge must remain training_only")
    return payload

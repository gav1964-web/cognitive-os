"""Build safe extraction proposals from Project Analyzer reports."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.dependency_extraction_policy import evaluate_dependency_policy


def build_extraction_proposal(
    *,
    project_dir: Path,
    analyzer_outputs: dict[str, Any],
    write_spec: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    project_report = dict(analyzer_outputs["project_map_report"])
    python_structure = dict(analyzer_outputs["extract_python_structure"])
    plan = dict(dict(project_report.get("answers", {})).get("6_runtime_extraction_readiness", {})).get(
        "minimal_extraction_plan", {}
    )
    candidates = list(dict(plan).get("capabilities_to_extract", []))
    ranked_candidates = _rank_candidates(candidates, python_structure)
    if not ranked_candidates:
        return {"status": "blocked", "reason": "no safe extraction candidate", "project": project_dir.as_posix()}
    functions = _function_index(python_structure)
    skipped_candidates = []
    selected = None
    function = None
    dependency_policy = None
    for candidate in ranked_candidates:
        candidate_function = _find_function(python_structure, candidate["path"], candidate["symbol"])
        candidate_policy = evaluate_dependency_policy(candidate_function, functions)
        if candidate_policy.status == "blocked":
            skipped_candidates.append(
                {
                    "selected": candidate,
                    "reason": "dependency_policy_blocked",
                    "dependency_policy": candidate_policy.to_dict(),
                }
            )
            continue
        selected = candidate
        function = candidate_function
        dependency_policy = candidate_policy
        break
    if selected is None or function is None or dependency_policy is None:
        return {
            "status": "blocked",
            "reason": "dependency_policy_blocked",
            "project": project_dir.as_posix(),
            "skipped_candidates": skipped_candidates,
        }
    spec = _spec_from_function(project_dir.name, selected, function, dependency_policy.to_dict())
    proposal = {
        "status": "ok",
        "kind": "safe_extraction_proposal",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "selected": selected,
        "safety": {
            "mode": "dry_run",
            "source_code_changes": False,
            "registry_changes": False,
            "reason": "first transformation step creates a reviewed Foundry spec, not an automatic refactor",
        },
        "evidence": {
            "function": function,
            "project_report_summary": project_report.get("summary", {}),
        },
        "candidate_fallback": {
            "used": bool(skipped_candidates),
            "skipped_count": len(skipped_candidates),
            "policy": "ranked candidates blocked by dependency policy are skipped before stopping the proposal",
        },
        "skipped_candidates": skipped_candidates,
        "proposed_spec": spec,
        "next_steps": [
            "review proposed_spec",
            "generate candidate in Foundry sandbox",
            "write contract and negative tests",
            "promote only after sandbox tests pass",
        ],
    }
    if write_spec:
        if root is None:
            raise ValueError("root is required when write_spec=True")
        spec_path = write_foundry_spec(root, spec)
        proposal["spec_path"] = spec_path.as_posix()
    return proposal


def write_extraction_proposal(root: Path, proposal: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "extractions"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    spec_id = dict(proposal.get("proposed_spec", {})).get("id", "extraction")
    path = out_dir / f"{spec_id}_{stamp}.json"
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_foundry_spec(root: Path, spec: dict[str, Any]) -> Path:
    path = root / "generated" / "specs" / f"{spec['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _select_candidate(candidates: list[dict[str, Any]], python_structure: dict[str, Any]) -> dict[str, str] | None:
    ranked = _rank_candidates(candidates, python_structure)
    return ranked[0] if ranked else None


def _rank_candidates(candidates: list[dict[str, Any]], python_structure: dict[str, Any]) -> list[dict[str, str]]:
    functions = _function_index(python_structure)
    ranked = []
    for index, row in enumerate(candidates):
        capability = str(row.get("capability") or "")
        if ":" not in capability or capability.startswith("[") or capability.startswith("run_application:"):
            continue
        path, symbol = capability.split(":", 1)
        function = functions.get((path, symbol))
        if not function:
            continue
        effects = set(function.get("side_effects", []))
        score = 0
        if not effects:
            score += 10
        if effects <= {"filesystem_read"}:
            score += 6
        if "pure transform" in str(row.get("why", "")).lower():
            score += 5
        policy_score = _candidate_policy_score(capability, function)
        score += policy_score
        score -= int(function.get("loc") or 0) // 20
        ranked.append(
            (
                score,
                index,
                {"capability": capability, "path": path, "symbol": symbol, "why": str(row.get("why") or "")},
            )
        )
    if not ranked:
        return []
    return [item[2] for item in sorted(ranked, key=lambda item: (-item[0], item[1], item[2]["capability"]))]


def _candidate_policy_score(capability: str, function: dict[str, Any]) -> int:
    lowered = capability.lower()
    symbol = lowered.rsplit(":", 1)[-1]
    args = " ".join(str(arg.get("name") or "") for arg in function.get("args", []))
    annotations = " ".join(str(arg.get("annotation") or "") for arg in function.get("args", []))
    text = " ".join([lowered, symbol, args, annotations]).lower()
    score = 0
    if any(token in symbol for token in ("parse", "normalize", "validate", "build_key", "cache_key")):
        score += 18
    if any(token in text for token in ("request", "response", "middleware", "http", "fastapi", "flask")):
        score -= 35
    if any(token in symbol for token in ("handler", "middleware", "endpoint")):
        score -= 20
    if function.get("is_async") or str(function.get("async", "")).lower() == "true":
        score -= 25
    return score


def _spec_from_function(
    project_name: str,
    selected: dict[str, str],
    function: dict[str, Any],
    dependency_policy: dict[str, Any],
) -> dict[str, Any]:
    spec_id = _safe_id(f"{project_name}_{selected['symbol']}")
    return {
        "id": spec_id,
        "purpose": f"Extract reusable capability from {selected['capability']}",
        "input_contract": _input_contract(function),
        "output_contract": _output_contract(function),
        "error_policy": {"invalid_input": "raise ValueError", "runtime_failure": "surface controlled error"},
        "side_effects": _side_effect_manifest(function),
        "quality_gate": _quality_gate(function),
        "dependency_policy": dependency_policy,
        "reusable": True,
        "source_extraction": {
            "project": project_name,
            "source": selected["capability"],
            "line": function.get("line"),
            "loc": function.get("loc"),
            "why": selected.get("why"),
        },
    }


def _input_contract(function: dict[str, Any]) -> dict[str, str]:
    args = function.get("args", [])
    if not args:
        return {"value": "string"}
    return {str(arg.get("name")): _contract_type(str(arg.get("annotation") or "string")) for arg in args}


def _output_contract(function: dict[str, Any]) -> dict[str, str]:
    annotation = str(function.get("returns") or "value")
    if not annotation or annotation == "None":
        return {"status": "string"}
    return {"result": _contract_type(annotation)}


def _side_effect_manifest(function: dict[str, Any]) -> dict[str, str]:
    effects = set(function.get("side_effects", []))
    filesystem = "read_only" if effects <= {"filesystem_read"} and effects else "none"
    if "filesystem" in effects:
        filesystem = "write_scoped"
    return {
        "filesystem": filesystem,
        "network": "allowlist" if "network" in effects else "none",
        "secrets": "none",
    }


def _quality_gate(function: dict[str, Any]) -> dict[str, Any]:
    sample_input = _sample_input(function)
    return {"sample_input": sample_input, "expected_output_shape": _output_contract(function)}


def _sample_input(function: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for arg in function.get("args", []):
        name = str(arg.get("name") or "value")
        result[name] = _sample_value(str(arg.get("annotation") or "string"), arg_name=name, function=function)
    return result or {"value": "sample"}


def _sample_value(annotation: str, *, arg_name: str, function: dict[str, Any]) -> object:
    lowered = annotation.lower()
    calls = {str(item) for item in function.get("calls", [])}
    if arg_name.lower() == "messages":
        return [{"role": "user", "content": "sample"}]
    if "list" in lowered and "dict" in lowered:
        return [{"value": " Sample "}]
    if "list" in lowered:
        if arg_name.endswith("rows") or any(str(call).endswith(".items") for call in calls):
            return [{"value": " Sample "}]
        return ["sample"]
    if "dict" in lowered or "model" in lowered or "request" in lowered or "response" in lowered:
        return {"value": "sample"}
    if "int" in lowered:
        return 1
    if "float" in lowered:
        return 1.0
    if "bool" in lowered:
        return True
    return "sample"


def _find_function(python_structure: dict[str, Any], path: str, symbol: str) -> dict[str, Any]:
    return _function_index(python_structure).get((path, symbol), {"path": path, "name": symbol})


def _function_index(python_structure: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    for file_summary in python_structure.get("files", []):
        for function in file_summary.get("functions", []):
            rows[(str(function.get("path")), str(function.get("name")))] = dict(function)
    return rows


def _contract_type(annotation: str) -> str:
    lowered = annotation.lower()
    if "int" in lowered:
        return "integer"
    if "float" in lowered:
        return "number"
    if "bool" in lowered:
        return "boolean"
    if "tuple" in lowered:
        return "array"
    if "list" in lowered:
        return "array"
    if "dict" in lowered or "model" in lowered or "request" in lowered or "response" in lowered:
        return "object"
    return "string"


def _safe_id(value: str) -> str:
    result = re.sub(r"[^a-z0-9_]+", "_", value.lower())
    result = re.sub(r"_+", "_", result).strip("_")
    if not result or not result[0].isalpha():
        result = f"capability_{result}"
    return result[:80]

"""Run exact-oracle L4.5 Programmer trials on isolated semantic mutations."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.programmer_executor import run_programmer_executor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--cases", default="benchmarks/programmer_l45_semantic_cases.json")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--label", default="programmer_l45_semantic")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run_trial(
        root=Path(args.root).resolve(),
        cases_path=Path(args.cases),
        offset=args.offset,
        limit=args.limit,
        case_ids=set(args.ids or []),
        label=args.label,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


def run_trial(
    *, root: Path, cases_path: Path, offset: int = 0, limit: int, label: str, write: bool,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    source_path = cases_path if cases_path.is_absolute() else root / cases_path
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    available = [dict(item) for item in list(payload.get("cases") or [])]
    if case_ids:
        available = [item for item in available if str(item.get("id")) in case_ids]
    cases = available[offset : offset + limit]
    provenance_root = root / str(payload.get("source_root") or "")
    for case in cases:
        case["provenance_status"] = _verify_provenance(provenance_root, case)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work_root = root / "artifacts" / "programmer_l45_semantic_trial" / stamp
    previous = os.environ.get("COGNITIVE_OS_EXECUTOR_USE_L45_LLM")
    os.environ["COGNITIVE_OS_EXECUTOR_USE_L45_LLM"] = "1"
    try:
        rows = [_run_case(root, work_root, case) for case in cases]
    finally:
        if previous is None:
            os.environ.pop("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", None)
        else:
            os.environ["COGNITIVE_OS_EXECUTOR_USE_L45_LLM"] = previous
    scores = [float(row["score"]) for row in rows]
    report = {
        "artifact_type": "ProgrammerL45SemanticTrial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "model_route": "external_l45_intent_resolver",
        "case_count": len(rows),
        "cases": rows,
        "summary": {
            "accepted": sum(row["status"] == "accepted" for row in rows),
            "minimum_score": min(scores) if scores else 0.0,
            "project_count": len({row["project"] for row in rows}),
            "candidate_applied": sum(row["checks"]["candidate_applied"] for row in rows),
            "source_code_changes": 0,
        },
    }
    report["status"] = "ok" if rows and all(row["status"] == "accepted" for row in rows) else "needs_review"
    if write:
        path = root / "artifacts" / "field_trials" / f"{label}_{stamp}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _run_case(root: Path, work_root: Path, case: dict[str, Any]) -> dict[str, Any]:
    case_dir = work_root / str(case["id"])
    project_dir = case_dir / "source"
    project_dir.mkdir(parents=True, exist_ok=True)
    source = str(case["source"])
    (project_dir / "main.py").write_text(source, encoding="utf-8")
    target = str(case["target"])
    examples = [dict(item) for item in list(case.get("examples") or [])]
    spec, plan, test_plan = _artifacts(case, target, examples)
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
        max_commands=1,
    )
    patch = _read(result.get("patch_package_path"))
    test_result = _read(result.get("test_result_path"))
    strategy = dict(patch.get("patch_strategy") or {})
    llm = dict(strategy.get("llm_strategy") or {})
    attempt = dict(patch.get("sandbox_candidate_attempt") or {})
    repair = dict(patch.get("sandbox_candidate_repair_attempt") or {})
    candidate = dict(strategy.get("sandbox_patch_candidate") or {})
    acceptance = dict(test_result.get("executable_acceptance_result") or {})
    checks = {
        "llm_proposed": llm.get("status") == "proposed",
        "recipe_proposed": llm.get("action") == "propose_patch_recipe",
        "candidate_applied": attempt.get("status") == "applied_in_sandbox" or repair.get("status") == "applied_in_sandbox",
        "executor_ok": result.get("status") == "ok",
        "acceptance_callable": dict(acceptance.get("summary") or {}).get("signal_strength") == "executable_callable",
        "acceptance_passed": acceptance.get("status") == "passed",
        "source_unchanged": (project_dir / "main.py").read_text(encoding="utf-8") == source,
    }
    passed = sum(bool(value) for value in checks.values())
    return {
        "id": case["id"],
        "project": case["project"],
        "provenance": case["provenance"],
        "provenance_status": case["provenance_status"],
        "fixture_relation": case.get("fixture_relation", "direct_semantic_mutation"),
        "target": target,
        "status": "accepted" if passed == len(checks) else "needs_review",
        "score": round(10.0 * passed / len(checks), 2),
        "checks": checks,
        "llm_action": llm.get("action"),
        "llm_reason": llm.get("reason"),
        "candidate_status": attempt.get("status"),
        "candidate_reason": attempt.get("reason"),
        "candidate_edit_format": candidate.get("edit_format"),
        "candidate_errors": list(candidate.get("errors") or []),
        "replacement_line_count": candidate.get("replacement_line_count", 0),
        "repair_status": repair.get("status"),
        "executor_status": result.get("status"),
        "acceptance_summary": acceptance.get("summary"),
    }


def _artifacts(
    case: dict[str, Any], target: str, examples: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    statement = str(case["statement"])
    obligations = [
        {
            "id": f"OBL-{index:03d}",
            "acceptance_id": f"AC-{index:03d}",
            "target": target,
            "kind": "positive_contract_case",
            "given": dict(example["given"]),
            "expect": {"return_value": example.get("expected")},
            "oracle": "literal_return_value_matches_semantic_trial",
        }
        for index, example in enumerate(examples, 1)
    ]
    obligations.append(
        {
            "id": "OBL-SCOPE",
            "acceptance_id": "side_effect_boundary",
            "target": target,
            "kind": "side_effect_scope_case",
            "given": {"declared_scope": "writable_scope_only"},
            "expect": {"no_writes_outside_declared_scope": True},
            "oracle": "changed_file_list_is_subset_of_writable_scope",
        }
    )
    spec = {
        "artifact_type": "TechnicalSpec",
        "role": "spec_writer",
        "goal": statement,
        "acceptance_criteria": [statement],
    }
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target, "mode": "sandbox_first"},
        "writable_scope": [target],
        "expected_files": [target.split(":", 1)[0]],
        "verification_commands": ["python -m compileall ."],
        "contract_binding": {"input_contract": _input_contract(examples)},
        "implementation_delta": {
            "artifact_type": "ImplementationDelta",
            "status": "semantic_synthesis_required",
            "intent": {"kind": "semantic_behavior_change", "statement": statement},
        },
    }
    test_plan = {"artifact_type": "TestPlan", "role": "tester", "executable_acceptance": {"obligations": obligations}}
    return spec, plan, test_plan


def _input_contract(examples: list[dict[str, Any]]) -> dict[str, str]:
    values = dict(examples[0].get("given") or {}) if examples else {}
    return {key: type(value).__name__ for key, value in values.items()}


def _verify_provenance(source_root: Path, case: dict[str, Any]) -> str:
    rel, separator, symbol = str(case.get("provenance") or "").partition(":")
    expected = str(case.get("provenance_ast_sha256") or "")
    path = source_root / str(case.get("project") or "") / rel
    if not separator or not expected or not path.is_file():
        raise ValueError(f"unverifiable provenance for {case.get('id')}")
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
    ]
    if not nodes:
        raise ValueError(f"provenance symbol missing for {case.get('id')}")
    actual = hashlib.sha256(ast.dump(nodes[0], include_attributes=False).encode()).hexdigest()
    if actual != expected:
        raise ValueError(f"provenance fingerprint mismatch for {case.get('id')}")
    return "verified_ast_fingerprint"


def _read(path_value: Any) -> dict[str, Any]:
    path = Path(str(path_value or ""))
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


if __name__ == "__main__":
    raise SystemExit(main())

"""Run blind exact-oracle trials for atomic composite Programmer edits."""

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
    parser.add_argument("--cases", default="benchmarks/programmer_l45_composite_cases.json")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--label", default="programmer_l45_composite")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run_trial(
        root=Path(args.root).resolve(),
        cases_path=Path(args.cases),
        limit=args.limit,
        label=args.label,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


def run_trial(*, root: Path, cases_path: Path, limit: int, label: str, write: bool) -> dict[str, Any]:
    source = cases_path if cases_path.is_absolute() else root / cases_path
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "programmer_l45_composite_cases.v1":
        raise ValueError("unsupported composite trial schema")
    cases = [dict(item) for item in list(payload.get("cases") or [])[:limit]]
    provenance_root = root / str(payload.get("source_root") or "")
    for case in cases:
        case["provenance_status"] = _verify_provenance(provenance_root, case)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work_root = root / "artifacts" / "programmer_l45_composite_trial" / stamp
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
        "artifact_type": "ProgrammerL45CompositeTrial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "model_route": "external_l45_intent_resolver",
        "case_count": len(rows),
        "cases": rows,
        "summary": {
            "accepted": sum(row["status"] == "accepted" for row in rows),
            "minimum_score": min(scores) if scores else 0.0,
            "project_count": len({row["project"] for row in rows}),
            "target_count": sum(int(row["target_count"]) for row in rows),
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
    project_dir = work_root / str(case["id"]) / "source"
    files = {str(path): str(content) for path, content in dict(case.get("files") or {}).items()}
    for path_text, content in files.items():
        path = project_dir / path_text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    edits = [dict(item) for item in list(case.get("edits") or [])]
    spec, plan, test_plan = _artifacts(case, edits, files)
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
    repair_candidate = dict(dict(patch.get("executor_repair_strategy") or {}).get("sandbox_patch_candidate") or {})
    acceptance = dict(test_result.get("executable_acceptance_result") or {})
    acceptance_summary = dict(acceptance.get("summary") or {})
    checks = {
        "llm_proposed": llm.get("status") == "proposed",
        "recipe_proposed": llm.get("action") == "propose_patch_recipe",
        "candidate_applied": attempt.get("status") == "applied_in_sandbox" or repair.get("status") == "applied_in_sandbox",
        "composite_edit_count": _applied_targets(patch, strategy, attempt) == {
            str(item.get("target") or "") for item in edits
        },
        "executor_ok": result.get("status") == "ok",
        "acceptance_callable": int(acceptance_summary.get("callable_harness_count") or 0) >= len(edits),
        "acceptance_passed": acceptance.get("status") == "passed",
        "source_unchanged": all((project_dir / path).read_text(encoding="utf-8") == content for path, content in files.items()),
    }
    passed = sum(bool(value) for value in checks.values())
    return {
        "id": case["id"],
        "project": case["project"],
        "fixture_relation": case.get("fixture_relation"),
        "provenance_status": case["provenance_status"],
        "target_count": len(edits),
        "targets": [str(item.get("target") or "") for item in edits],
        "status": "accepted" if passed == len(checks) else "needs_review",
        "score": round(10.0 * passed / len(checks), 2),
        "checks": checks,
        "llm_action": llm.get("action"),
        "llm_reason": llm.get("reason"),
        "candidate_status": attempt.get("status"),
        "candidate_reason": attempt.get("reason"),
        "candidate_errors": list(candidate.get("errors") or []),
        "candidate_edit_count": candidate.get("edit_count", 0),
        "repair_edit_count": repair_candidate.get("edit_count", 0),
        "repair_attempt_count": len(list(patch.get("sandbox_candidate_repair_attempts") or [])),
        "repair_status": repair.get("status"),
        "executor_status": result.get("status"),
        "acceptance_summary": acceptance_summary,
    }


def _artifacts(
    case: dict[str, Any], edits: list[dict[str, Any]], files: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    statements = [str(item.get("statement") or "") for item in edits]
    target = str(edits[0]["target"])
    obligations = []
    for edit_index, edit in enumerate(edits, 1):
        for example_index, example in enumerate(list(edit.get("examples") or []), 1):
            obligations.append(
                {
                    "id": f"OBL-{edit_index:02d}-{example_index:02d}",
                    "acceptance_id": f"AC-{edit_index:02d}-{example_index:02d}",
                    "target": edit["target"],
                    "kind": "positive_contract_case",
                    "given": dict(example["given"]),
                    "expect": {"return_value": example.get("expected")},
                    "oracle": "literal_return_value_matches_composite_trial",
                }
            )
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
        "goal": " Apply both required changes atomically. ".join(statements),
        "acceptance_criteria": statements,
    }
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target, "mode": "sandbox_first"},
        "writable_scope": list(files),
        "expected_files": list(files),
        "change_plan": [
            {"id": f"CHANGE-{index:03d}", "target": edit["target"], "instruction": edit["statement"]}
            for index, edit in enumerate(edits, 1)
        ],
        "verification_commands": ["python -m compileall ."],
        "implementation_delta": {
            "artifact_type": "ImplementationDelta",
            "status": "semantic_synthesis_required",
            "intent": {"kind": "atomic_composite_behavior_change", "statements": statements},
        },
    }
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "executable_acceptance": {"obligations": obligations},
    }
    return spec, plan, test_plan


def _verify_provenance(source_root: Path, case: dict[str, Any]) -> str:
    for edit in list(case.get("edits") or []):
        rel, separator, symbol = str(edit.get("provenance") or "").partition(":")
        path = source_root / str(case.get("project") or "") / rel
        expected = str(edit.get("provenance_ast_sha256") or "")
        if not separator or not expected or not path.is_file():
            raise ValueError(f"unverifiable provenance for {case.get('id')}")
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        nodes = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
        ]
        actual = hashlib.sha256(ast.dump(nodes[0], include_attributes=False).encode()).hexdigest() if nodes else ""
        if actual != expected:
            raise ValueError(f"provenance fingerprint mismatch for {case.get('id')}:{symbol}")
    return "verified_ast_fingerprints"


def _read(path_value: Any) -> dict[str, Any]:
    path = Path(str(path_value or ""))
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _applied_targets(
    patch: dict[str, Any], initial_strategy: dict[str, Any], initial_attempt: dict[str, Any]
) -> set[str]:
    strategies = [initial_strategy, *list(patch.get("executor_repair_strategies") or [])]
    attempts = [initial_attempt, *list(patch.get("sandbox_candidate_repair_attempts") or [])]
    targets: set[str] = set()
    for strategy, attempt in zip(strategies, attempts):
        if dict(attempt).get("status") != "applied_in_sandbox":
            continue
        recipe = dict(dict(strategy).get("llm_strategy") or {}).get("patch_recipe_hypothesis") or {}
        edits = [dict(item) for item in list(dict(recipe).get("edits") or []) if isinstance(item, dict)]
        if edits:
            targets.update(str(item.get("target_symbol") or "") for item in edits)
        elif recipe.get("target_symbol"):
            targets.add(str(recipe["target_symbol"]))
    return targets - {""}


if __name__ == "__main__":
    raise SystemExit(main())

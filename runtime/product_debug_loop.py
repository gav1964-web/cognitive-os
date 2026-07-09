"""Executable bounded Stage 3 product debug loop."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_scaffold import run_project_verification
from .greenfield_templates import acceptance_covered
from .product_slice import _documentation_review, _scenario_verification
from .programmer_project_review import review_programmer_project


def run_product_debug_loop(
    *,
    package: dict[str, Any],
    reference: dict[str, Any],
    max_attempts: int = 1,
) -> dict[str, Any]:
    attempts = []
    current = dict(package)
    for attempt in range(1, max_attempts + 1):
        analysis = analyze_product_slice_failure(current)
        plan = build_product_rework_plan(analysis, current)
        result = apply_product_rework_plan(current, reference, plan)
        attempts.append(
            {
                "attempt": attempt,
                "failure_analysis": analysis,
                "rework_plan": plan,
                "result": result["result"],
            }
        )
        current = result["package"]
        if _package_clean(current) or plan["status"] != "ready":
            break
    return {
        "artifact_type": "ProductDebugLoop",
        "created_at": _now(),
        "max_attempts": max_attempts,
        "attempts": attempts,
        "final_status": "ok" if _package_clean(current) else "needs_rework",
        "final_package": current,
        "invariants": {
            "sandbox_only": True,
            "source_tree_changes": False,
            "registry_changes": False,
            "bounded_rework": True,
            "stage2_package_is_execution_engine": True,
        },
    }


def analyze_product_slice_failure(package: dict[str, Any]) -> dict[str, Any]:
    system_type = str(package.get("system_type") or "unknown")
    docs = _documentation_review(package)
    scenarios = _scenario_verification(system_type, package)
    blockers = []
    if docs["status"] != "ok":
        blockers.append("documentation_review")
    if scenarios["status"] != "covered":
        blockers.append("scenario_verification")
    return {
        "artifact_type": "ProductFailureAnalysis",
        "status": "needs_rework" if blockers else "clean",
        "blockers": blockers,
        "documentation_review": docs,
        "scenario_verification": scenarios,
        "repairable": set(blockers).issubset({"documentation_review", "scenario_verification"}),
    }


def build_product_rework_plan(analysis: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    actions = []
    blockers = set(analysis.get("blockers", []))
    if "documentation_review" in blockers:
        actions.append({"type": "rewrite_readme_from_verified_package", "target": "README.md"})
    if "scenario_verification" in blockers:
        actions.append({"type": "add_missing_scenario_test_inside_generated_package", "target": "tests"})
    if actions:
        actions.append({"type": "rerun_project_scoped_verification", "target": "project"})
    return {
        "artifact_type": "ProductReworkPlan",
        "status": "ready" if actions and analysis.get("repairable") else "blocked",
        "scope": "isolated_generated_package",
        "actions": actions,
        "forbidden_actions": ["edit_user_source_tree", "edit_registry", "promote_candidate"],
        "reason": "bounded product-scenario repair" if actions else "no product rework needed",
    }


def apply_product_rework_plan(
    package: dict[str, Any],
    reference: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    if plan.get("status") != "ready":
        return {"result": {"status": "blocked", "reason": plan.get("reason")}, "package": package}
    project_dir = Path(str(package.get("project_dir") or ""))
    case_name = _case_name(package)
    applied = []
    for action in plan.get("actions", []):
        action_type = action.get("type")
        if action_type == "rewrite_readme_from_verified_package":
            if _rewrite_readme(project_dir, package, reference):
                applied.append(action_type)
        elif action_type == "add_missing_scenario_test_inside_generated_package":
            if _add_missing_scenario_test(project_dir, case_name):
                applied.append(action_type)
        elif action_type == "rerun_project_scoped_verification":
            continue
    updated = _refresh_package(package, reference, project_dir, case_name)
    return {
        "result": {
            "status": "applied",
            "applied_actions": applied,
            "verification": dict(updated.get("verification_report", {})).get("status"),
        },
        "package": updated,
    }


def _refresh_package(package: dict[str, Any], reference: dict[str, Any], project_dir: Path, case_name: str) -> dict[str, Any]:
    verification = run_project_verification(project_dir)
    scaffold = {
        "artifact_type": "GreenfieldScaffold",
        "case": case_name,
        "prompt": package.get("prompt"),
        "project_dir": project_dir.as_posix(),
        "files": [{"path": path, "status": "written"} for path in dict(package.get("source_code", {})).get("files", [])],
        "verification": verification,
        "acceptance_covered": acceptance_covered(case_name, verification),
        "limitations": package.get("known_limitations", []),
    }
    tester = review_programmer_project(scaffold=scaffold, reference=reference)
    updated = dict(package)
    updated["tester_review"] = tester
    updated["tests"] = tester.get("coverage", {})
    updated["verification_report"] = verification
    updated["status"] = "ok" if tester.get("recommendation") in {"approve", "approve_with_risks"} else "blocked"
    updated["release_decision"] = _release_decision(updated)
    updated["documentation"] = _documentation_pack(updated)
    return updated


def _documentation_pack(package: dict[str, Any]) -> dict[str, Any]:
    docs = dict(package.get("documentation", {}))
    readme = docs.get("readme") or (Path(str(package.get("project_dir") or "")) / "README.md").as_posix()
    run_instructions = list(docs.get("run_instructions", [])) or ["python -m compileall -b .", "python -m pytest tests -q"]
    system_type = str(package.get("system_type") or "")
    if system_type == "fastapi_service" and not any("uvicorn" in item for item in run_instructions):
        app_module = _app_module(package) or "package"
        run_instructions.append(f"uvicorn {app_module}.app:app --app-dir src")
    return {
        "readme": readme,
        "run_instructions": run_instructions,
        "verification_summary": {
            "tester_recommendation": dict(package.get("tester_review", {})).get("recommendation"),
            "missing_acceptance": dict(package.get("tests", {})).get("missing_acceptance", []),
        },
    }


def _release_decision(package: dict[str, Any]) -> dict[str, str]:
    if package.get("status") == "ok" and dict(package.get("tests", {})).get("missing_acceptance") == []:
        return {"decision": "release_ready", "reason": "tester approved generated package"}
    return {"decision": "blocked", "reason": "product debug loop still has missing evidence"}


def _rewrite_readme(project_dir: Path, package: dict[str, Any], reference: dict[str, Any]) -> bool:
    path = project_dir / "README.md"
    prompt = str(reference.get("prompt") or package.get("prompt") or "")
    commands = list(dict(package.get("documentation", {})).get("run_instructions", []))
    if not commands:
        commands = ["python -m compileall -b .", "python -m pytest tests -q"]
        app_module = _app_module(package)
        if app_module:
            commands.append(f"uvicorn {app_module}.app:app --app-dir src")
    run_lines = "\n".join(f"- `{item}`" for item in commands)
    content = f"# Generated package\n\nPrompt: {prompt}\n\n## Run\n\n{run_lines}\n"
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _app_module(package: dict[str, Any]) -> str | None:
    for path in dict(package.get("source_code", {})).get("files", []):
        value = str(path)
        if value.startswith("src/") and value.endswith("/app.py"):
            return value.split("/")[1]
    return None


def _add_missing_scenario_test(project_dir: Path, case_name: str) -> bool:
    if case_name == "fastapi_kv_store":
        path = project_dir / "tests" / "test_api.py"
        marker = "def test_missing_item_returns_404"
        snippet = (
            "\n\ndef test_missing_item_returns_404():\n"
            "    client = TestClient(app)\n"
            "    assert client.get('/items/missing').status_code == 404\n"
        )
        return _append_if_missing(path, marker, snippet)
    if case_name == "fastapi_csv_aggregator":
        path = project_dir / "tests" / "test_api.py"
        marker = "def test_invalid_csv_returns_400"
        snippet = (
            "\n\ndef test_invalid_csv_returns_400():\n"
            "    client = TestClient(app)\n"
            "    response = client.post('/aggregate', json={'csv_text': 'bad', 'output_path': 'out.json'})\n"
            "    assert response.status_code == 400\n"
        )
        return _append_if_missing(path, marker, snippet)
    return False


def _append_if_missing(path: Path, marker: str, snippet: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    path.write_text(text.rstrip() + snippet + "\n", encoding="utf-8")
    return True


def _case_name(package: dict[str, Any]) -> str:
    return str(dict(dict(package.get("tester_review", {})).get("review_target", {})).get("case") or "")


def _package_clean(package: dict[str, Any]) -> bool:
    return analyze_product_slice_failure(package)["status"] == "clean" and package.get("status") == "ok"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

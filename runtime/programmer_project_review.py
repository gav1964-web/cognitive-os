"""Generate a programmer scaffold and let tester inspect the real project."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_scaffold import create_greenfield_scaffold


def run_programmer_project_review(
    *,
    root: Path,
    curriculum_dir: Path,
    case_name: str,
    write: bool = False,
) -> dict[str, Any]:
    reference_path = curriculum_dir / case_name / "teacher_reference.json"
    if not reference_path.is_file():
        raise FileNotFoundError(f"unknown programmer curriculum case: {case_name}")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    scaffold = create_greenfield_scaffold(root=root, case_name=case_name, reference=reference)
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    report = {
        "status": "ok" if tester_review["recommendation"] in {"approve", "approve_with_risks"} else "needs_rework",
        "artifact_type": "ProgrammerProjectReviewRun",
        "created_at": _now(),
        "case": case_name,
        "prompt": reference.get("prompt"),
        "programmer_artifact": scaffold,
        "tester_review": tester_review,
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "source_tree_changes": False,
            "registry_changes": False,
            "reviewer_role": "tester",
        },
    }
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    return report


def review_programmer_project(*, scaffold: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    files = [str(row.get("path")) for row in scaffold.get("files", [])]
    verification = dict(scaffold.get("verification", {}))
    acceptance = list(scaffold.get("acceptance_covered", []))
    expected_acceptance = [str(item) for item in reference.get("acceptance_criteria", [])]
    project_dir = Path(str(scaffold.get("project_dir", "")))
    file_texts = _read_project_texts(project_dir, files)
    checks = _checks(files, verification, acceptance, expected_acceptance, file_texts, reference)
    findings = _findings(checks, files)
    risks = _risks(scaffold, checks)
    return {
        "artifact_type": "TesterProjectReview",
        "role": "tester",
        "status": "ok",
        "created_at": _now(),
        "project_dir": scaffold.get("project_dir"),
        "review_target": {
            "case": scaffold.get("case"),
            "artifact_type": scaffold.get("artifact_type"),
            "prompt": scaffold.get("prompt"),
        },
        "verification": verification,
        "coverage": {
            "expected_acceptance": expected_acceptance,
            "covered_acceptance": acceptance,
            "missing_acceptance": [item for item in expected_acceptance if item not in acceptance],
            "project_file_count": len(files),
            "source_files": [item for item in files if item.startswith("src/")],
            "test_files": [item for item in files if item.startswith("tests/") and item.endswith(".py")],
            "edge_evidence": _edge_evidence(file_texts),
        },
        "checks": checks,
        "findings": findings,
        "risk_assessment": risks,
        "recommendation": _recommendation(checks, findings, risks),
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["edit_source_tree", "edit_registry", "promote_candidate"],
    }


def _checks(
    files: list[str],
    verification: dict[str, Any],
    acceptance: list[str],
    expected_acceptance: list[str],
    file_texts: dict[str, str],
    reference: dict[str, Any],
) -> dict[str, bool]:
    test_files = [item for item in files if item.startswith("tests/") and item.endswith(".py")]
    source_files = [item for item in files if item.startswith("src/") and item.endswith(".py")]
    test_text = "\n".join(file_texts.get(item, "") for item in test_files)
    source_text = "\n".join(file_texts.get(item, "") for item in source_files)
    pyproject = file_texts.get("pyproject.toml", "")
    readme = file_texts.get("README.md", "")
    return {
        "has_pyproject": "pyproject.toml" in files,
        "has_readme": "README.md" in files,
        "has_dependency_policy": _has_dependency_policy(source_text, pyproject),
        "readme_has_run_command": _readme_has_run_command(source_text, readme),
        "has_source_package": bool(source_files),
        "has_cli_entrypoint": _is_api_project(source_text) or any(item.endswith("/cli.py") for item in source_files),
        "cli_uses_argparse": _is_api_project(source_text) or ("import argparse" in source_text and "parse_args" in source_text),
        "cli_accepts_input_output": _is_api_project(source_text) or ("add_argument('input')" in source_text and "add_argument('output')" in source_text),
        "has_fastapi_app": not _is_api_project(source_text) or ("FastAPI(" in source_text and "@app." in source_text),
        "has_api_tests": not _is_api_project(source_text) or ("TestClient" in test_text and ("/aggregate" in test_text or "/items" in test_text)),
        "has_controlled_api_error": not _is_api_project(source_text) or ("HTTPException" in source_text and "status_code=" in source_text),
        "has_tests": bool(test_files),
        "has_core_test": any(item.endswith(("test_core.py", "test_aggregator.py", "test_store.py")) for item in test_files),
        "has_cli_test": _is_api_project(source_text) or any(item.endswith("test_cli.py") for item in test_files),
        "has_fixture": _is_api_project(source_text) or any("/fixtures/" in item.replace("\\", "/") for item in files),
        "has_negative_or_edge_test": _has_negative_or_edge_test(test_text, file_texts),
        "readme_mentions_prompt": _readme_mentions_prompt(file_texts, reference),
        "readme_behavior_aligned": _readme_behavior_aligned(file_texts, reference),
        "verification_passed": verification.get("status") == "passed",
        "acceptance_complete": not [item for item in expected_acceptance if item not in acceptance],
        "project_scoped_verification": verification.get("project_scoped") is True,
    }


def _findings(checks: dict[str, bool], files: list[str]) -> list[dict[str, str]]:
    findings = []
    for key, passed in checks.items():
        if not passed:
            findings.append({"code": key, "severity": "high", "description": f"Project review check failed: {key}."})
    if not findings:
        findings.append(
            {
                "code": "no_blocking_findings",
                "severity": "info",
                "description": f"Generated project has {len(files)} files, tests and project-scoped verification passed.",
            }
        )
    return findings


def _risks(scaffold: dict[str, Any], checks: dict[str, bool]) -> list[dict[str, str]]:
    risks = []
    if scaffold.get("case") in {"ixbt_news_scraper", "url_status_checker_cli"}:
        risks.append(
            {
                "target": "network",
                "severity": "medium",
                "risk": "Default tests use fixtures or injectable fetchers; live network behavior remains a separate smoke.",
                "mitigation": "Keep live smoke optional and rate-limited before production use.",
            }
        )
    if not checks.get("verification_passed"):
        risks.append(
            {
                "target": "verification",
                "severity": "high",
                "risk": "Generated project tests did not pass.",
                "mitigation": "Return to programmer with pytest stderr and failing artifact path.",
            }
        )
    return risks or [
        {
            "target": "project",
            "severity": "low",
            "risk": "No material tester risk detected for current curriculum scope.",
            "mitigation": "Expand with negative and integration tests as the prompt corpus grows.",
        }
    ]


def _recommendation(checks: dict[str, bool], findings: list[dict[str, str]], risks: list[dict[str, str]]) -> str:
    if any(item.get("severity") == "high" for item in findings):
        return "request_rework"
    if any(item.get("severity") == "medium" for item in risks):
        return "approve_with_risks"
    return "approve"


def _read_project_texts(project_dir: Path, files: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in files:
        path = (project_dir / item).resolve()
        try:
            path.relative_to(project_dir.resolve())
        except ValueError:
            continue
        if path.suffix.lower() not in {".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".html", ".toml"}:
            continue
        if path.is_file():
            texts[item] = path.read_text(encoding="utf-8", errors="replace")
    return texts


def _has_negative_or_edge_test(test_text: str, file_texts: dict[str, str]) -> bool:
    fixture_text = "\n".join(value for key, value in file_texts.items() if "/fixtures/" in key.replace("\\", "/"))
    markers = ["malformed", "invalid", "unsupported", "missing", "empty", "skipped", "path traversal", "not-json", "stats('')"]
    return any(marker in test_text.lower() or marker in fixture_text.lower() for marker in markers)


def _is_api_project(source_text: str) -> bool:
    return "FastAPI(" in source_text


def _has_dependency_policy(source_text: str, pyproject: str) -> bool:
    if _is_api_project(source_text):
        return "dependencies" in pyproject and "fastapi" in pyproject.lower()
    return bool(pyproject)


def _readme_has_run_command(source_text: str, readme: str) -> bool:
    lower = readme.lower()
    if _is_api_project(source_text):
        return "uvicorn" in lower and "pytest" in lower and "app:app" in lower
    return "pytest" in lower


def _readme_mentions_prompt(file_texts: dict[str, str], reference: dict[str, Any]) -> bool:
    readme = file_texts.get("README.md", "")
    prompt = str(reference.get("prompt", ""))
    return bool(readme and prompt and prompt in readme)


def _readme_behavior_aligned(file_texts: dict[str, str], reference: dict[str, Any]) -> bool:
    readme = file_texts.get("README.md", "").lower()
    prompt = str(reference.get("prompt", "")).lower()
    keywords = [word.strip(".,:;()") for word in prompt.split() if len(word.strip(".,:;()")) >= 5]
    return bool(readme and keywords and sum(1 for word in keywords[:8] if word in readme) >= 2)


def _edge_evidence(file_texts: dict[str, str]) -> list[dict[str, str]]:
    evidence = []
    for path, text in sorted(file_texts.items()):
        lower = text.lower()
        if any(marker in lower for marker in ["jsondecodeerror", "not-json", "unsupported", "empty", "path traversal"]):
            evidence.append({"path": path, "kind": "negative_or_edge_case"})
        if "argparse" in lower and "parse_args" in lower:
            evidence.append({"path": path, "kind": "cli_usability"})
    return evidence[:12]


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "programmer_project_reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{report['case']}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

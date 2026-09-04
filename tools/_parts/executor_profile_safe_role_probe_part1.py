"""Run role-produced Executor probes for profile-safe identity transforms."""

from __future__ import annotations

import argparse
import ast
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.architecture_decision_policy import load_architecture_decision_policy
from runtime.contract_transform_contract_profiles import contract_profile_for_operator, contract_profile_hint
from runtime.contract_transform_mutation import identity_mutation_source, observed_operator
from runtime.implementation_plan_builder import build_implementation_plan
from runtime.generated_stub_admission import inspect_generated_function_stubs
from runtime.programmer_acceptance_gate import enforce_prepared_patch_acceptance
from runtime.programmer_executor import run_programmer_executor
from runtime.programmer_transformation_trial_quality import evaluate_transformation_case, transformation_summary
from runtime.programmer_verification import run_test_result
from runtime.project_benchmark import analyze_project
from runtime.review_findings_builder import build_review_findings
from runtime.role_project_type_evaluation import load_role_project_type_policy
from runtime.role_artifact_quality import (
    evaluate_technical_spec,
    evaluate_implementation_plan,
    evaluate_review_findings,
    evaluate_test_plan,
)
from runtime.technical_spec_builder import build_technical_spec
from runtime.test_plan_builder import build_test_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="executor_profile_safe_role_probe")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-per-project", type=int, default=3)
    parser.add_argument(
        "--stratum",
        choices=(
            "library_pure_transform", "cli_local_tool", "web_api_middleware",
            "sdk_provider_integration",
            "stateful_service_database",
            "async_worker_scheduler",
            "external_process_io",
            "framework_plugin_build",
            "data_tabular_pipeline",
            "scientific_compute",
            "ml_inference",
            "ml_training_checkpoint",
            "llm_multi_agent",
        ),
        default="library_pure_transform",
    )
    parser.add_argument("--cli-interface", choices=("argv_json", "stdin_json", "file_json"), default="argv_json")
    parser.add_argument("--web-interface", choices=("post_json", "get_query", "header_json"), default="post_json")
    parser.add_argument(
        "--provider-interface",
        choices=("data_envelope", "choices_envelope", "paged_envelope"),
        default="data_envelope",
    )
    parser.add_argument(
        "--stateful-interface",
        choices=("insert_read", "update_read", "transaction_read"),
        default="insert_read",
    )
    parser.add_argument(
        "--async-interface",
        choices=("await_once", "gather_batch", "queue_worker"),
        default="await_once",
    )
    parser.add_argument(
        "--io-interface",
        choices=("file_roundtrip", "subprocess_pipe", "zip_archive"),
        default="file_roundtrip",
    )
    parser.add_argument(
        "--framework-interface",
        choices=("plugin_hook", "package_build", "code_generation", "docs_render"),
        default="plugin_hook",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--project-name", action="append", default=[], help="Restrict source lineage to named projects")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    report = run_profile_safe_role_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        limit=args.limit,
        max_per_project=args.max_per_project,
        project_stratum=args.stratum,
        cli_interface=args.cli_interface,
        web_interface=args.web_interface,
        provider_interface=args.provider_interface,
        stateful_interface=args.stateful_interface,
        async_interface=args.async_interface,
        io_interface=args.io_interface,
        framework_interface=args.framework_interface,
        project_names=set(args.project_name),
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_profile_safe_role_probe(
    *,
    root: Path,
    projects_dir: Path,
    label: str,
    limit: int = 20,
    max_per_project: int = 3,
    project_stratum: str = "library_pure_transform",
    cli_interface: str = "argv_json",
    web_interface: str = "post_json",
    provider_interface: str = "data_envelope",
    stateful_interface: str = "insert_read",
    async_interface: str = "await_once",
    io_interface: str = "file_roundtrip",
    framework_interface: str = "plugin_hook",
    project_names: set[str] | None = None,
) -> dict[str, Any]:
    rows = _discover_rows(
        projects_dir, limit=limit, max_per_project=max_per_project,
        project_names=project_names,
    )
    rows = [{**row, "source_lineage": projects_dir.resolve().as_posix()} for row in rows]
    if project_stratum in DOMAIN_BENCHMARK_RECIPES:
        requested = set(project_names or set())
        if requested:
            lineage_rows = _discover_domain_lineage_rows(projects_dir, requested)
            anchored = {str(row.get("project") or "") for row in lineage_rows}
            rows = lineage_rows + [
                row for row in rows if str(row.get("project") or "") not in anchored
            ]
    rows = _domain_benchmark_rows(rows, project_stratum)
    work_root = root / "artifacts" / "executor_profile_safe_role_probe" / _stamp()
    cases = [
        _run_case_safe(
            root, work_root, row, project_stratum=project_stratum,
            cli_interface=cli_interface, web_interface=web_interface,
            provider_interface=provider_interface,
            stateful_interface=stateful_interface,
            async_interface=async_interface,
            io_interface=io_interface,
            framework_interface=framework_interface,
        )
        for row in rows
    ]
    summary = transformation_summary(cases)
    stub_admissions = [dict(case.get("generated_function_stub_admission") or {}) for case in cases]
    summary["generated_stub_count"] = sum(
        len(admission.get("violations") or []) for admission in stub_admissions
    )
    summary["stub_parse_failure_count"] = sum(
        len(admission.get("parse_failures") or []) for admission in stub_admissions
    )
    summary["stub_admission_passed"] = bool(stub_admissions) and all(
        admission.get("status") == "passed" for admission in stub_admissions
    )
    return {
        "artifact_type": "ExecutorProfileSafeRoleProbe",
        "status": "ok" if cases and summary["accepted"] == len(cases)
        and summary["stub_admission_passed"] else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_lineage": projects_dir.resolve().as_posix(),
        "case_count": len(cases),
        "summary": summary,
        "invariants": {
            "source_projects_modified": summary["source_code_changes"],
            "mode": "derived_mutation_benchmark",
            "maturity_scope": project_stratum,
        },
        "cases": cases,
    }


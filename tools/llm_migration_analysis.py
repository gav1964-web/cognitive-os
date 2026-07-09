"""Analyze a project for direct external LLM migration points."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEXT_EXTENSIONS = {".py", ".md", ".toml", ".txt", ".env", ".bat", ".ps1", ".json"}
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "map_install_package", "static"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--target-model", default="GigaChat-2-Pro")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    project_dir = Path(args.project_dir).resolve()
    report = analyze_llm_migration(project_dir=project_dir, target_model=args.target_model)
    if args.write:
        report["report_path"] = _write_report(root, report).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"ok", "needs_migration"} else 2


def analyze_llm_migration(*, project_dir: Path, target_model: str) -> dict[str, Any]:
    files = _read_text_files(project_dir)
    evidence = _collect_evidence(files)
    recommendations = _recommendations(evidence, target_model)
    blockers = _blockers(evidence)
    return {
        "artifact_type": "LlmMigrationAnalysis",
        "status": "needs_migration" if evidence["llm_files"] else "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "target_model": target_model,
        "current_state": {
            "llm_files": evidence["llm_files"],
            "default_urls": evidence["default_urls"],
            "default_models": evidence["default_models"],
            "request_calls": evidence["request_calls"],
            "cli_flags": evidence["cli_flags"],
            "cache_keys": evidence["cache_keys"],
            "availability_checks": evidence["availability_checks"],
            "fallbacks": evidence["fallbacks"],
        },
        "recommendations": recommendations,
        "blockers": blockers,
        "migration_plan": _migration_plan(target_model),
        "acceptance_criteria": _acceptance_criteria(target_model),
        "non_goals": [
            "Do not edit user source automatically.",
            "Do not remove rule-based fallback until direct provider tests pass.",
            "Do not hardcode secrets or tokens in the repository.",
        ],
    }


def _read_text_files(project_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(project_dir).parts):
            continue
        if path.stat().st_size > 500_000:
            continue
        rel = path.relative_to(project_dir).as_posix()
        files[rel] = path.read_text(encoding="utf-8", errors="replace")
    return files


def _collect_evidence(files: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    evidence = {
        "llm_files": [],
        "default_urls": [],
        "default_models": [],
        "request_calls": [],
        "cli_flags": [],
        "cache_keys": [],
        "availability_checks": [],
        "fallbacks": [],
    }
    for rel, text in files.items():
        lower = text.lower()
        is_llm_file = any(marker in lower for marker in ("llm", "chat/completions", "gigachat", "qwen", "openai"))
        if is_llm_file:
            evidence["llm_files"].append({"file": rel})
        for line_no, line in _matching_lines(text, r"DEFAULT_.*LLM.*URL|chat/completions|127\.0\.0\.1"):
            if _line_mentions_llm(line):
                evidence["default_urls"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"DEFAULT_.*LLM.*MODEL|--llm-model|model"):
            if "model" in line.lower() and ("llm" in line.lower() or "qwen" in line.lower() or "--llm-model" in line.lower()):
                evidence["default_models"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"requests\.post|httpx\.post|Authorization|Bearer"):
            if is_llm_file:
                evidence["request_calls"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"--llm-|no-llm|llm_scope|llm-scope"):
            evidence["cli_flags"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"batch_key|cache_key|LLM_CACHE|prompt_version"):
            evidence["cache_keys"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"check_available|raise_for_status|status_code"):
            if is_llm_file:
                evidence["availability_checks"].append({"file": rel, "line": line_no, "text": line.strip()})
        for line_no, line in _matching_lines(text, r"no-llm|fallback|using rule-based|rules"):
            evidence["fallbacks"].append({"file": rel, "line": line_no, "text": line.strip()})
    return evidence


def _matching_lines(text: str, pattern: str) -> list[tuple[int, str]]:
    regex = re.compile(pattern, re.IGNORECASE)
    return [(index, line) for index, line in enumerate(text.splitlines(), 1) if regex.search(line)]


def _line_mentions_llm(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in ("llm", "qwen", "openai", "gigachat", "chat/completions", "8000"))


def _recommendations(evidence: dict[str, list[dict[str, Any]]], target_model: str) -> list[dict[str, str]]:
    rows = [
        {
            "id": "R1",
            "title": "Introduce provider-specific direct client",
            "detail": f"Replace local OpenAI-compatible default endpoint with a GigaChat client profile using model `{target_model}`.",
        },
        {
            "id": "R2",
            "title": "Move provider config to environment",
            "detail": "Use env/config for base URL, OAuth/token source, scope, timeout and TLS settings; keep CLI overrides.",
        },
        {
            "id": "R3",
            "title": "Preserve extraction contract and cache semantics",
            "detail": "Keep JSON-only response parsing, prompt versioning and cache keys including provider/model/prompt version.",
        },
        {
            "id": "R4",
            "title": "Add provider boundary tests",
            "detail": "Mock direct GigaChat responses, auth failures, rate limits, invalid JSON and timeout fallback.",
        },
    ]
    if evidence["fallbacks"]:
        rows.append({"id": "R5", "title": "Keep rules fallback", "detail": "Retain rule-based parser when provider is unavailable."})
    return rows


def _blockers(evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    blockers = []
    if not evidence["request_calls"]:
        blockers.append({"code": "no_http_client_boundary", "detail": "No direct HTTP LLM call site was found."})
    if not evidence["cli_flags"]:
        blockers.append({"code": "no_runtime_config_surface", "detail": "No CLI/config flags for LLM provider were found."})
    return blockers


def _migration_plan(target_model: str) -> list[dict[str, str]]:
    return [
        {"step": "1", "action": "Extract LlmExtractor transport into an LlmClient interface.", "scope": "import_indoc.py"},
        {"step": "2", "action": f"Add GigaChat direct implementation with model `{target_model}`.", "scope": "new provider module or class"},
        {"step": "3", "action": "Replace local default URL/model with env-driven GigaChat defaults.", "scope": "config and CLI"},
        {"step": "4", "action": "Add mocked provider tests and preserve rule fallback behavior.", "scope": "tests"},
        {"step": "5", "action": "Run a small fixture import and compare event counts/cache hits.", "scope": "verification"},
    ]


def _acceptance_criteria(target_model: str) -> list[str]:
    return [
        f"default model can be set to {target_model} without local proxy assumptions",
        "no provider token is committed to source",
        "LLM cache key changes when provider/model changes",
        "provider unavailable path falls back to rules or reports controlled failure",
        "mocked direct-provider extraction returns valid events JSON",
    ]


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "project_llm_migration"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"llm_migration_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

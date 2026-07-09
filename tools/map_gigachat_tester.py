"""Tester-role probe for map direct GigaChat integration."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = run_map_gigachat_tester(
        root=Path(args.root).resolve(),
        project_dir=Path(args.project_dir).resolve(),
        live=args.live,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["recommendation"] in {"approve", "approve_with_risks"} else 1


def run_map_gigachat_tester(*, root: Path, project_dir: Path, live: bool = False, write: bool = False) -> dict[str, Any]:
    source = project_dir / "import_indoc.py"
    if not source.is_file():
        raise FileNotFoundError(source)

    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}
    commands = []

    compile_result = _run([sys.executable, "-m", "py_compile", str(source)], cwd=project_dir)
    commands.append(compile_result)
    checks["compile_passed"] = compile_result["status"] == "passed"

    help_result = _run([sys.executable, "import_indoc.py", "--help"], cwd=project_dir)
    commands.append(help_result)
    help_text = help_result.get("stdout", "")
    checks["help_mentions_gigachat"] = "GigaChat" in help_text and "Qwen" not in help_text

    text = source.read_text(encoding="utf-8", errors="replace")
    checks["direct_gigachat_default"] = "GigaChat-2-Pro" in text and "http://127.0.0.1:8000/v1/chat/completions" not in text
    checks["client_secret_alias"] = "GIGACHAT_CLIENT_SECRET" in text
    checks["tls_policy_env"] = "GIGACHAT_VERIFY_SSL" in text
    checks["rules_fallback_present"] = "--no-llm" in text and "rule-based" in text
    checks["schema_detail_preserved"] = "населенный пункт без префикса" in text
    checks["progress_label_migrated"] = "GigaChat batch" in text and "Qwen batch" not in text

    fallback_result = _run([sys.executable, "import_indoc.py", "--no-llm"], cwd=project_dir, timeout=120)
    commands.append(_trim_command(fallback_result))
    checks["rule_based_import_passed"] = fallback_result["status"] == "passed" and "Wrote incidents.json" in fallback_result.get("stdout", "")
    evidence["rule_based_summary"] = _extract_json_tail(fallback_result.get("stdout", ""))

    live_result = {"status": "skipped", "reason": "live flag not set"}
    if live:
        live_result = _live_smoke(project_dir)
    evidence["live_smoke"] = live_result
    checks["live_smoke_passed"] = live_result.get("status") == "passed" if live else True

    findings = _findings(checks, live=live)
    risks = _risks(checks, live=live, live_result=live_result)
    recommendation = _recommendation(findings, risks)
    report = {
        "artifact_type": "TesterProjectReview",
        "role": "tester",
        "target": "map_gigachat_integration",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": project_dir.as_posix(),
        "checks": checks,
        "verification": {"status": "passed" if all(checks.values()) else "failed", "commands": commands},
        "coverage": {
            "covered_acceptance": [name for name, passed in checks.items() if passed],
            "missing_acceptance": [name for name, passed in checks.items() if not passed],
        },
        "evidence": evidence,
        "findings": findings,
        "risk_assessment": risks,
        "recommendation": recommendation,
        "forbidden_actions_observed": [],
        "secret_policy": {
            "secrets_read_from_env": live,
            "secrets_written_to_artifacts": False,
            "secret_values_redacted": True,
        },
    }
    if write:
        out_dir = root / "artifacts" / "tester_reviews"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"map_gigachat_tester_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _live_smoke(project_dir: Path) -> dict[str, Any]:
    if not (os.environ.get("GIGACHAT_AUTH_KEY") or os.environ.get("GIGACHAT_CLIENT_SECRET") or os.environ.get("GIGACHAT_ACCESS_TOKEN")):
        return {"status": "failed", "reason": "missing_gigachat_credentials"}
    script = r'''
import json
import sys
import tempfile
from pathlib import Path
import urllib3

sys.path.insert(0, r"{project_dir}")
from import_indoc import DEFAULT_LLM_MODEL, DEFAULT_LLM_URL, LlmExtractor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
rows = [{{"line": 1, "time": "12:30", "text": "В Курске подавлен БПЛА самолетного типа, пострадавших нет."}}]
with tempfile.TemporaryDirectory() as d:
    client = LlmExtractor(DEFAULT_LLM_URL, DEFAULT_LLM_MODEL, timeout=60, cache_path=Path(d) / "cache.json")
    ok, message = client.check_available(timeout=30)
    events = client.extract_batch("2026-06-18", rows) if ok else []
    print(json.dumps({{"ok": ok, "message": message[:200], "event_count": len(events), "events": events[:1]}}, ensure_ascii=False))
'''.format(project_dir=project_dir.as_posix())
    result = _run([sys.executable, "-c", script], cwd=project_dir, timeout=120)
    payload = _parse_json_object(result.get("stdout", ""))
    return {
        "status": "passed" if result["status"] == "passed" and payload.get("ok") is True and payload.get("event_count", 0) >= 1 else "failed",
        "returncode": result["returncode"],
        "payload": payload,
        "stderr_tail": result.get("stderr_tail", ""),
    }


def _run(command: list[str], *, cwd: Path, timeout: int = 60) -> dict[str, Any]:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {
        "command": " ".join(command[:3]) + (" ..." if len(command) > 3 else ""),
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stdout_tail": result.stdout[-1200:],
        "stderr_tail": result.stderr[-1200:],
    }


def _trim_command(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "stdout"}


def _extract_json_tail(text: str) -> dict[str, Any]:
    start = text.rfind("{")
    if start < 0:
        return {}
    return _parse_json_object(text[start:])


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text.strip())
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _findings(checks: dict[str, bool], *, live: bool) -> list[dict[str, str]]:
    findings = [
        {"code": name, "severity": "high", "description": f"Tester check failed: {name}."}
        for name, passed in checks.items()
        if not passed
    ]
    if not findings:
        findings.append({"code": "no_blocking_findings", "severity": "info", "description": "Map GigaChat integration checks passed."})
    if not live:
        findings.append({"code": "live_smoke_skipped", "severity": "medium", "description": "Live GigaChat smoke was not requested."})
    return findings


def _risks(checks: dict[str, bool], *, live: bool, live_result: dict[str, Any]) -> list[dict[str, str]]:
    risks = []
    if not live:
        risks.append({"target": "provider", "severity": "medium", "risk": "Direct provider path was not live-tested.", "mitigation": "Run with --live and env credentials."})
    if live and live_result.get("status") != "passed":
        risks.append({"target": "provider", "severity": "high", "risk": "Live provider smoke failed.", "mitigation": "Inspect TLS, credentials and provider response."})
    if checks.get("rule_based_import_passed") and live:
        risks.append({"target": "cost", "severity": "low", "risk": "Full live import may consume provider quota.", "mitigation": "Keep full-corpus live runs explicit and bounded."})
    return risks or [{"target": "project", "severity": "low", "risk": "No material tester risk detected.", "mitigation": "Keep regression smoke in CI without secrets."}]


def _recommendation(findings: list[dict[str, str]], risks: list[dict[str, str]]) -> str:
    if any(item["severity"] == "high" for item in findings + risks):
        return "request_rework"
    if any(item["severity"] == "medium" for item in findings + risks):
        return "approve_with_risks"
    return "approve"


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate configured Cognitive OS LLM profiles."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.l45_semantic_benchmark import run_l45_semantic_benchmark
from runtime.local_inference import LocalInferenceConfig, call_json_chat, load_llm_profiles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--benchmark-l45", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = build_llm_profile_eval(
        root=root,
        profile_ids=args.profile,
        smoke=args.smoke,
        benchmark_l45=args.benchmark_l45,
    )
    if args.write:
        report.update(write_report(root, report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def build_llm_profile_eval(
    *,
    root: Path,
    profile_ids: list[str] | None = None,
    smoke: bool = False,
    benchmark_l45: bool = False,
) -> dict[str, Any]:
    payload = load_llm_profiles(str(root / "config" / "llm_profiles.json"))
    profiles = dict(payload.get("profiles") or {})
    selected = profile_ids or ["local_l35", "external_l45_intent_resolver"]
    rows = [_profile_row(profile_id, dict(profiles.get(profile_id) or {}), smoke=smoke) for profile_id in selected]
    benchmark = _benchmark_l45(root, profiles) if benchmark_l45 else None
    failed = [row for row in rows if row["status"] == "failed"]
    if benchmark and benchmark["status"] == "failed":
        failed.append({"profile_id": "external_l45_intent_resolver"})
    return {
        "artifact_type": "LlmProfileEvalReport",
        "status": "failed" if failed else "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": rows,
        "l45_benchmark": benchmark,
        "summary": {
            "profile_count": len(rows),
            "smoke_passed": sum(1 for row in rows if dict(row.get("smoke") or {}).get("status") == "ok"),
            "benchmark_passed": benchmark is not None and benchmark.get("status") == "ok",
        },
    }


def write_report(root: Path, report: dict[str, Any]) -> dict[str, str]:
    out_dir = root / "artifacts" / "llm_profile_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"llm_profile_eval_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _profile_row(profile_id: str, profile: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    if not profile:
        return {"profile_id": profile_id, "status": "failed", "errors": ["profile_missing"]}
    config = LocalInferenceConfig(
        base_url=str(profile.get("base_url") or "").rstrip("/"),
        model=str(profile.get("model") or ""),
        timeout_seconds=float(profile.get("timeout_seconds") or 20),
        response_format=bool(profile.get("response_format")),
        api_key=os.environ.get(str(profile.get("api_key_env") or "")) or None,
        provider_label=str(profile.get("provider_label") or profile_id),
    )
    smoke_report = _smoke(config) if smoke else {"status": "skipped"}
    return {
        "profile_id": profile_id,
        "status": "failed" if smoke_report["status"] == "failed" else "ok",
        "base_url": config.base_url,
        "model": config.model,
        "provider_label": config.provider_label,
        "response_format": config.response_format,
        "smoke": smoke_report,
    }


def _smoke(config: LocalInferenceConfig) -> dict[str, Any]:
    try:
        result = call_json_chat(
            [
                {"role": "system", "content": "Return only a JSON object."},
                {"role": "user", "content": "Return {\"ok\": true, \"quality\": \"smoke\"}."},
            ],
            config=config,
        )
        return {"status": "ok", "result": result}
    except Exception as exc:  # noqa: BLE001 - live provider smoke is diagnostic.
        return {"status": "failed", "error": str(exc)[:500]}


def _benchmark_l45(root: Path, profiles: dict[str, Any]) -> dict[str, Any]:
    profile = dict(profiles.get("external_l45_intent_resolver") or {})
    config = LocalInferenceConfig(
        base_url=str(profile.get("base_url") or "http://127.0.0.1:8000/v1").rstrip("/"),
        model=str(profile.get("model") or "deepseek/deepseek-chat"),
        timeout_seconds=float(profile.get("timeout_seconds") or 60),
        response_format=bool(profile.get("response_format")),
        api_key=os.environ.get(str(profile.get("api_key_env") or "")) or None,
        provider_label=str(profile.get("provider_label") or "external_l45_intent_resolver"),
    )
    report = run_l45_semantic_benchmark(
        root=root,
        write=False,
        use_model=True,
        model_quality_mode="model_propose_only",
        config=config,
    )
    return {
        "status": report.get("status"),
        "model": config.model,
        "summary": dict(report.get("summary") or {}),
    }


if __name__ == "__main__":
    raise SystemExit(main())

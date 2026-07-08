"""Clone GitHub projects and run Project Rebuild Trial on each."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.project_rebuild import run_project_rebuild_trial
    from runtime.project_probe_env import prepare_probe_env

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--corpus-dir", default="artifacts/github_rebuild_corpus")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prepare-probe-env", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    corpus_dir = _resolve(root, args.corpus_dir)
    clone_dir = corpus_dir / "repos"
    rebuild_dir = corpus_dir / "rebuilt"
    clone_dir.mkdir(parents=True, exist_ok=True)
    rebuild_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for repo in args.repo:
        rows.append(_run_one(root, clone_dir, rebuild_dir, repo, args.force, args.prepare_probe_env, run_project_rebuild_trial, prepare_probe_env))
    report = {
        "status": "ok",
        "kind": "github_rebuild_corpus",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_count": len(rows),
        "summary": _summary(rows),
        "results": rows,
    }
    out_dir = root / "artifacts" / "rebuild_trials"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = out_dir / f"github_rebuild_corpus_{stamp}.json"
    md_path = out_dir / f"github_rebuild_corpus_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    report["report_path"] = json_path.as_posix()
    report["markdown_path"] = md_path.as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_one(root: Path, clone_dir: Path, rebuild_dir: Path, repo: str, force: bool, prepare_env: bool, runner: Any, env_preparer: Any) -> dict[str, Any]:
    name = _safe_repo_name(repo)
    source = clone_dir / name
    rebuilt = rebuild_dir / f"{name}_x"
    clone = _clone_repo(repo, source, clone_dir, force)
    if clone["status"] != "ok":
        return {"repo": repo, "status": "clone_failed", "clone": clone}
    trial = runner(root=root, source_dir=source, output_dir=rebuilt, force=True)
    comparison = dict(trial.get("comparison", {}))
    behavior = dict(comparison.get("behavior", {}))
    env = dict(comparison.get("probe_env", {}))
    prepared = env_preparer(
        env_dir=root / "artifacts" / "probe_envs" / name,
        readiness=env,
        allow_install=prepare_env,
    )
    rerun = False
    if prepared.get("status") == "prepared" and prepared.get("python"):
        trial = runner(root=root, source_dir=source, output_dir=rebuilt, force=True, source_python=Path(str(prepared["python"])))
        comparison = dict(trial.get("comparison", {}))
        behavior = dict(comparison.get("behavior", {}))
        env = dict(comparison.get("probe_env", {}))
        rerun = True
    depth = _behavior_depth(behavior)
    quality = _quality_scores(trial, comparison, depth)
    return {
        "repo": repo,
        "status": trial.get("status"),
        "score": comparison.get("score"),
        "quality": quality,
        "corpus_verdict": _corpus_verdict(quality),
        "missing": comparison.get("missing", []),
        "behavior_status": behavior.get("status"),
        "behavior_summary": behavior.get("summary"),
        "behavior_depth": depth,
        "behavior_blueprints": len(dict(trial.get("spec", {})).get("behavior_blueprints", [])),
        "probe_env_status": env.get("status"),
        "probe_env_prepare": prepared,
        "probe_env_rerun": rerun,
        "missing_modules": env.get("missing_modules", []),
        "target": trial.get("rebuilt_project"),
        "trial_report": trial.get("report_path"),
        "clone": clone,
    }


def _clone_repo(repo: str, target: Path, clone_root: Path, force: bool) -> dict[str, Any]:
    if target.exists() and force:
        if clone_root.resolve() not in target.resolve().parents:
            return {"status": "blocked", "reason": "target outside clone root", "target": target.as_posix()}
        shutil.rmtree(target)
    if target.exists():
        return {"status": "ok", "reason": "already_exists", "path": target.as_posix()}
    url = repo if repo.startswith("http") else f"https://github.com/{repo}.git"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", url, str(target)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return {"status": "error", "url": url, "stderr": result.stderr[-1000:]}
    return {"status": "ok", "url": url, "path": target.as_posix()}


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row.get("status") == "ok"]
    needs = [row for row in rows if row.get("status") == "needs_work"]
    failed = [row for row in rows if row.get("status") not in {"ok", "needs_work"}]
    probes = sum(int(dict(row.get("behavior_summary") or {}).get("total") or 0) for row in rows)
    probe_failed = sum(int(dict(row.get("behavior_summary") or {}).get("failed") or 0) for row in rows)
    http = sum(int(dict(row.get("behavior_depth") or {}).get("http_probes") or 0) for row in rows)
    manifest = sum(int(dict(row.get("behavior_depth") or {}).get("manifest_probes") or 0) for row in rows)
    source_ok = sum(int(dict(row.get("behavior_depth") or {}).get("source_ok") or 0) for row in rows)
    source_unavailable = sum(int(dict(row.get("behavior_depth") or {}).get("source_unavailable") or 0) for row in rows)
    blocked_env = [row for row in rows if row.get("probe_env_status") == "blocked"]
    prepared_env = [row for row in rows if dict(row.get("probe_env_prepare") or {}).get("status") == "prepared"]
    missing_modules = sorted({str(module) for row in rows for module in row.get("missing_modules", [])})
    verdicts = {}
    for row in rows:
        verdict = str(row.get("corpus_verdict") or "unknown")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    averages = _average_quality(rows)
    return {
        "ok": len(ok),
        "needs_work": len(needs),
        "failed": len(failed),
        "behavior_probes": probes,
        "behavior_probe_failed": probe_failed,
        "http_probes": http,
        "manifest_probes": manifest,
        "source_ok": source_ok,
        "source_unavailable": source_unavailable,
        "probe_env_blocked": len(blocked_env),
        "probe_env_prepared": len(prepared_env),
        "missing_modules": missing_modules,
        "blueprints": sum(int(row.get("behavior_blueprints") or 0) for row in rows),
        "average_score": round(sum(float(row.get("score") or 0) for row in rows) / len(rows), 3) if rows else 0,
        "average_quality": averages,
        "verdicts": verdicts,
    }


def _quality_scores(trial: dict[str, Any], comparison: dict[str, Any], depth: dict[str, int]) -> dict[str, float]:
    spec = dict(trial.get("spec") or {})
    checks = dict(comparison.get("checks") or {})
    analysis_parts = [
        bool(spec.get("main_task")),
        bool(spec.get("entrypoints")),
        bool(spec.get("supported_scenarios")),
        bool(spec.get("core_capabilities") or spec.get("routes")),
    ]
    spec_parts = [
        bool(spec.get("artifact_type") == "ProjectRebuildSpec"),
        bool(spec.get("target_name")),
        bool(spec.get("quality_targets")),
        bool(spec.get("routes") or spec.get("core_capabilities")),
    ]
    scaffold_keys = ["has_app_entrypoint", "has_readme", "has_contract_tests", "compiles", "contract_tests_pass"]
    scaffold_parts = [checks.get(key) is True for key in scaffold_keys]
    http = int(depth.get("http_probes") or 0)
    manifest = int(depth.get("manifest_probes") or 0)
    source_ok = int(depth.get("source_ok") or 0)
    if http:
        behavior_score = source_ok / http
    elif manifest:
        behavior_score = 0.35
    else:
        behavior_score = 0.0
    return {
        "analysis_score": _ratio(analysis_parts),
        "spec_score": _ratio(spec_parts),
        "scaffold_score": _ratio(scaffold_parts),
        "behavior_score": round(behavior_score, 3),
        "confidence": round((_ratio(analysis_parts) + _ratio(spec_parts) + _ratio(scaffold_parts) + behavior_score) / 4, 3),
    }


def _corpus_verdict(quality: dict[str, float]) -> str:
    behavior = float(quality.get("behavior_score") or 0)
    confidence = float(quality.get("confidence") or 0)
    if behavior >= 0.8 and confidence >= 0.85:
        return "behavior_checked"
    if confidence >= 0.7:
        return "shape_checked"
    return "needs_review"


def _average_quality(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ["analysis_score", "spec_score", "scaffold_score", "behavior_score", "confidence"]
    if not rows:
        return {key: 0.0 for key in keys}
    return {
        key: round(sum(float(dict(row.get("quality") or {}).get(key) or 0) for row in rows) / len(rows), 3)
        for key in keys
    }


def _ratio(parts: list[bool]) -> float:
    return round(sum(1 for item in parts if item) / len(parts), 3) if parts else 0.0


def _behavior_depth(behavior: dict[str, Any]) -> dict[str, int]:
    depth = {"http_probes": 0, "manifest_probes": 0, "source_ok": 0, "source_unavailable": 0}
    for case in behavior.get("cases", []):
        probe = dict(case.get("probe") or {})
        source = dict(case.get("source") or {})
        if probe.get("kind") == "http":
            depth["http_probes"] += 1
            if source.get("status") == "ok":
                depth["source_ok"] += 1
            else:
                depth["source_unavailable"] += 1
        elif probe.get("kind") == "capability_manifest":
            depth["manifest_probes"] += 1
    return depth


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# GitHub Rebuild Corpus", "", f"- Status: `{report['status']}`", f"- Projects: `{report['repo_count']}`"]
    summary = dict(report.get("summary", {}))
    lines.extend(
        [
            f"- OK: `{summary.get('ok')}`",
            f"- Needs work: `{summary.get('needs_work')}`",
            f"- Behavior probes: `{summary.get('behavior_probes')}` / failed `{summary.get('behavior_probe_failed')}`",
            f"- HTTP probes: `{summary.get('http_probes')}`",
            f"- Manifest probes: `{summary.get('manifest_probes')}`",
            f"- Source executed: `{summary.get('source_ok')}` / unavailable `{summary.get('source_unavailable')}`",
            f"- Probe env blocked: `{summary.get('probe_env_blocked')}`",
            f"- Probe env prepared: `{summary.get('probe_env_prepared')}`",
            f"- Missing modules: `{', '.join(summary.get('missing_modules') or [])}`",
            f"- Blueprints: `{summary.get('blueprints')}`",
            f"- Verdicts: `{summary.get('verdicts')}`",
            f"- Average quality: `{summary.get('average_quality')}`",
            "",
            "| Repo | Verdict | Conf | A/S/R/B | Probes | HTTP | Src OK | Missing |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report.get("results", []):
        behavior = dict(row.get("behavior_summary") or {})
        depth = dict(row.get("behavior_depth") or {})
        quality = dict(row.get("quality") or {})
        probes = f"{behavior.get('passed', 0)}/{behavior.get('total', 0)}"
        missing = ", ".join(str(item) for item in row.get("missing", []))
        quartet = (
            f"{quality.get('analysis_score', 0)}/"
            f"{quality.get('spec_score', 0)}/"
            f"{quality.get('scaffold_score', 0)}/"
            f"{quality.get('behavior_score', 0)}"
        )
        lines.append(
            f"| `{row.get('repo')}` | `{row.get('corpus_verdict')}` | `{quality.get('confidence')}` | `{quartet}` | "
            f"`{probes}` | `{depth.get('http_probes', 0)}` | `{depth.get('source_ok', 0)}` | {missing} |"
        )
    return "\n".join(lines) + "\n"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _safe_repo_name(repo: str) -> str:
    value = repo.removesuffix(".git").replace("https://github.com/", "")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


if __name__ == "__main__":
    raise SystemExit(main())

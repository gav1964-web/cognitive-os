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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.github_rebuild_corpus_report import (
    _behavior_depth,
    _corpus_verdict,
    _markdown,
    _quality_scores,
    _summary,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = REPO_ROOT
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
    prepared_runs = []
    rerun = False
    for _ in range(3):
        prepared = env_preparer(
            env_dir=root / "artifacts" / "probe_envs" / name,
            readiness=env,
            allow_install=prepare_env,
        )
        prepared_runs.append(prepared)
        if prepared.get("status") != "prepared" or not prepared.get("python"):
            break
        trial = runner(root=root, source_dir=source, output_dir=rebuilt, force=True, source_python=Path(str(prepared["python"])))
        comparison = dict(trial.get("comparison", {}))
        behavior = dict(comparison.get("behavior", {}))
        env = dict(comparison.get("probe_env", {}))
        rerun = True
    depth = _behavior_depth(behavior)
    quality = _quality_scores(trial, comparison, depth)
    legacy_score = comparison.get("score")
    return {
        "repo": repo,
        "status": trial.get("status"),
        "score": quality.get("conservative_score"),
        "legacy_score": legacy_score,
        "quality": quality,
        "corpus_verdict": _corpus_verdict(quality),
        "missing": comparison.get("missing", []),
        "behavior_status": behavior.get("status"),
        "behavior_summary": behavior.get("summary"),
        "behavior_depth": depth,
        "behavior_blueprints": len(dict(trial.get("spec", {})).get("behavior_blueprints", [])),
        "probe_env_status": env.get("status"),
        "probe_env_prepare": prepared_runs[-1] if prepared_runs else {},
        "probe_env_prepare_runs": prepared_runs,
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


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _safe_repo_name(repo: str) -> str:
    value = repo.removesuffix(".git").replace("https://github.com/", "")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


if __name__ == "__main__":
    raise SystemExit(main())

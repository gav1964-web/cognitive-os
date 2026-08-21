"""Freeze and clone a reproducible GitLab blind corpus."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.gitlab_corpus_search import search_page as _search_page
    from tools.gitlab_corpus_search import search_stratum
except ModuleNotFoundError:  # Direct script execution exposes tools/ on sys.path.
    from gitlab_corpus_search import search_page as _search_page
    from gitlab_corpus_search import search_stratum


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "gitlab_blind_corpus_strata.json"
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("select", "clone", "replace-failed"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    corpus = _resolve(root, args.corpus_dir)
    if args.phase == "select":
        report = select_corpus(root, corpus, args.iteration, Path(args.policy).resolve())
    elif args.phase == "clone":
        report = clone_corpus(corpus, force=args.force)
    else:
        report = replace_failed(root, corpus)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def select_corpus(root: Path, corpus: Path, iteration: int, policy_path: Path) -> dict[str, Any]:
    selection_path = corpus / "selection.json"
    if selection_path.exists():
        raise RuntimeError("selection is already frozen; choose a new corpus directory")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    known_names, known_repos = known_projects(root / "artifacts")
    selected: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    requested_by_stratum: dict[str, int] = {}
    claimed_names = set(known_names)
    claimed_repos = set(known_repos)
    for stratum in policy["strata"]:
        count = int(policy["projects_per_stratum"])
        requested_by_stratum[str(stratum["id"])] = count
        candidates = _search_stratum(
            stratum, policy, excluded_names=claimed_names, excluded_repos=claimed_repos, needed=count
        )
        rows = [
            row for row in candidates
            if _unseen(row, claimed_names, claimed_repos) and _eligible(row, policy)
        ]
        for row in rows[:count]:
            row["stratum"] = str(stratum["id"])
            selected.append(row)
            claimed_names.add(row["full_name"].lower())
            claimed_repos.add(_repo_key(row["full_name"]))
        overflow.extend({**row, "stratum": str(stratum["id"])} for row in rows[count:])
    requested_total = sum(requested_by_stratum.values())
    for row in sorted(overflow, key=lambda item: (-item["stars"], item["full_name"].lower())):
        if len(selected) >= requested_total:
            break
        if not _unseen(row, claimed_names, claimed_repos):
            continue
        selected.append(row)
        claimed_names.add(row["full_name"].lower())
        claimed_repos.add(_repo_key(row["full_name"]))
    if len(selected) < requested_total:
        raise RuntimeError(f"not enough unseen projects across strata: {len(selected)} < {requested_total}")
    corpus.mkdir(parents=True, exist_ok=False)
    payload = {
        "artifact_type": "GitLabBlindCorpusSelection",
        "created_at": _now(),
        "selection_frozen": True,
        "iteration": iteration,
        "known_blacklist_count": len(known_names),
        "known_repository_name_count": len(known_repos),
        "project_count": len(selected),
        "requested_by_stratum": requested_by_stratum,
        "selected_by_stratum": _count_by_stratum(selected),
        "policy": policy,
        "projects": selected,
    }
    selection_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "selection_path": selection_path.as_posix(), **_selection_summary(payload)}


def _count_by_stratum(projects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for project in projects:
        key = str(project.get("stratum") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def clone_corpus(corpus: Path, *, force: bool = False) -> dict[str, Any]:
    selection_path = corpus / "selection.json"
    if not selection_path.exists():
        raise RuntimeError("selection.json must be frozen before clone phase")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("selection_frozen") is not True:
        raise RuntimeError("selection is not frozen")
    source_dir = corpus / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    projects = selection["projects"]
    rows: list[dict[str, Any]] = []
    for index, project in enumerate(projects, start=1):
        print(f"[{index}/{len(projects)}] cloning {project['full_name']}", file=sys.stderr, flush=True)
        rows.append(_clone_one(source_dir, project, force=force))
        _write_clone_report(corpus, selection_path, projects, rows, status="running")
    status = "ok" if all(row["status"] == "ok" for row in rows) else "failed"
    report = _write_clone_report(corpus, selection_path, projects, rows, status=status)
    return report


def _write_clone_report(
    corpus: Path, selection_path: Path, projects: list[dict[str, Any]],
    rows: list[dict[str, Any]], *, status: str,
) -> dict[str, Any]:
    report = {
        "artifact_type": "GitLabBlindCorpusCloneReport", "status": status,
        "created_at": _now(), "selection_path": selection_path.as_posix(),
        "project_count": len(projects), "processed": len(rows),
        "cloned": sum(row["status"] == "ok" for row in rows),
        "failed": sum(row["status"] != "ok" for row in rows), "results": rows,
    }
    (corpus / "clone_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def replace_failed(root: Path, corpus: Path) -> dict[str, Any]:
    effective_path = corpus / "effective_selection.json"
    selection_path = effective_path if effective_path.exists() else corpus / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    clone_report = json.loads((corpus / "clone_report.json").read_text(encoding="utf-8"))
    failed = {row["full_name"] for row in clone_report["results"] if row["status"] != "ok"}
    known_names, known_repos = known_projects(root / "artifacts")
    replacements: list[dict[str, Any]] = []
    effective = [dict(row) for row in selection["projects"] if row["full_name"] not in failed]
    strata = {row["id"]: row for row in selection["policy"]["strata"]}
    source_dir = corpus / "src"
    for original in (row for row in selection["projects"] if row["full_name"] in failed):
        original_dir = source_dir / str(original["full_name"]).replace("/", "__")
        if original_dir.exists():
            _safe_remove_checkout(source_dir, original_dir)
        candidates = _search_stratum(
            strata[original["stratum"]], selection["policy"], excluded_names=known_names,
            excluded_repos=known_repos, needed=5,
        )
        attempts: list[dict[str, Any]] = []
        replacement = None
        for candidate in candidates:
            if not _unseen(candidate, known_names, known_repos) or not _eligible(candidate, selection["policy"]):
                continue
            known_names.add(str(candidate["full_name"]).lower()); known_repos.add(_repo_key(str(candidate["full_name"])))
            candidate["stratum"] = original["stratum"]
            result = _clone_one(source_dir, candidate, force=False)
            attempts.append(result)
            if result["status"] == "ok":
                replacement = candidate
                break
            failed_dir = Path(result["path"])
            if failed_dir.exists():
                _safe_remove_checkout(source_dir, failed_dir)
        if replacement is None:
            raise RuntimeError(f"no cloneable replacement for {original['full_name']}")
        effective.append(replacement)
        replacements.append({"original": original, "replacement": replacement, "attempts": attempts})
    replacement_path = corpus / "replacement_report.json"
    previous = json.loads(replacement_path.read_text(encoding="utf-8")).get("replacements", []) if replacement_path.exists() else []
    payload = {
        "artifact_type": "GitLabBlindCorpusReplacementReport", "status": "ok",
        "created_at": _now(), "replacements": [*previous, *replacements],
    }
    replacement_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    effective_payload = {**selection, "artifact_type": "GitLabBlindCorpusEffectiveSelection",
                         "source_selection": "selection.json", "projects": effective,
                         "project_count": len(effective)}
    (corpus / "effective_selection.json").write_text(
        json.dumps(effective_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"status": "ok", "project_count": len(effective), "replaced": len(replacements)}


def known_projects(artifacts: Path) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    repos: set[str] = set()
    selections = []
    for name in ("selection.json", "effective_selection.json"):
        selections.extend(artifacts.rglob(name) if artifacts.is_dir() else [])
    for selection in selections:
        try:
            payload = json.loads(selection.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in payload.get("projects", []):
            full_name = str(row.get("full_name") or "").lower()
            if full_name:
                names.add(full_name)
                repos.add(_repo_key(full_name))
    return names, repos


def _search_stratum(
    stratum: dict[str, Any],
    policy: dict[str, Any],
    *,
    excluded_names: set[str],
    excluded_repos: set[str],
    needed: int,
) -> list[dict[str, Any]]:
    return search_stratum(
        stratum, policy, excluded_names=excluded_names, excluded_repos=excluded_repos,
        needed=needed, project_row=_project_row, unseen=_unseen, eligible=_eligible,
    )


def _project_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "gitlab_id": int(item["id"]),
        "full_name": str(item["path_with_namespace"]),
        "clone_url": str(item["http_url_to_repo"]),
        "stars": int(item.get("star_count") or 0),
        "default_branch": str(item.get("default_branch") or ""),
        "html_url": str(item.get("web_url") or ""),
        "description": str(item.get("description") or ""),
        "topics": sorted(str(topic) for topic in item.get("topics", [])),
        "last_activity_at": str(item.get("last_activity_at") or ""),
        "empty_repo": bool(item.get("empty_repo")),
    }


def _eligible(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    if row["stars"] < int(policy["minimum_stars"]) or row.get("empty_repo"):
        return False
    name = row["full_name"].lower().replace("-", "_")
    description = row["description"].lower()
    if any(token.replace("-", "_") in name for token in policy.get("excluded_name_tokens", [])):
        return False
    if any(token in description for token in policy.get("excluded_description_tokens", [])):
        return False
    year = str(row.get("last_activity_at") or "")[:4]
    return year.isdigit() and int(year) >= int(policy.get("minimum_recent_year") or 2020)


def _unseen(row: dict[str, Any], names: set[str], repos: set[str]) -> bool:
    return row["full_name"].lower() not in names and _repo_key(row["full_name"]) not in repos


def _repo_key(full_name: str) -> str:
    return full_name.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower().removesuffix(".git")


def _clone_one(source_dir: Path, project: dict[str, Any], *, force: bool) -> dict[str, Any]:
    destination = source_dir / str(project["full_name"]).replace("/", "__")
    if destination.exists() and not force and _checkout_ready(destination):
        return _clone_result(project, destination, reused=True)
    if destination.exists():
        _safe_remove_checkout(source_dir, destination)
    command = [
        "git", "-c", "core.longpaths=true", "-c", "http.lowSpeedLimit=1000",
        "-c", "http.lowSpeedTime=30", "clone", "--depth", "1", "--filter=blob:none",
        str(project["clone_url"]), str(destination),
    ]
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as log:
        returncode = _run_clone(command, log)
        if returncode is None:
            return _clone_failure(project, destination, "clone_timeout", -1, log)
        if returncode != 0:
            return _clone_failure(project, destination, "clone_failed", returncode, log)
    return _clone_result(project, destination, reused=False)


def _run_clone(command: list[str], log: Any) -> int | None:
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log)
    try:
        return process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30,
            )
        else:
            process.kill()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        return None


def _clone_failure(
    project: dict[str, Any], destination: Path, status: str, returncode: int, log: Any,
) -> dict[str, Any]:
    log.seek(0)
    return {
        "full_name": project["full_name"], "status": status, "path": destination.as_posix(),
        "returncode": returncode, "stderr_tail": log.read()[-800:],
    }


def _safe_remove_checkout(source_dir: Path, destination: Path) -> None:
    source = source_dir.resolve()
    target = destination.resolve()
    if target.parent != source or target == source:
        raise RuntimeError(f"refusing to remove checkout outside corpus source: {target}")
    shutil.rmtree(target, onerror=_remove_readonly)


def _remove_readonly(function: Any, path: str, _: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _clone_result(project: dict[str, Any], destination: Path, *, reused: bool) -> dict[str, Any]:
    sha = subprocess.run(
        ["git", "-c", f"safe.directory={destination.as_posix()}", "-C", str(destination),
         "rev-parse", "HEAD"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=True,
    ).stdout.strip()
    return {
        "full_name": project["full_name"], "status": "ok", "path": destination.as_posix(),
        "commit_sha": sha, "reused": reused,
    }


def _checkout_ready(destination: Path) -> bool:
    if not (destination / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "-c", f"safe.directory={destination.as_posix()}", "-C", str(destination),
         "rev-parse", "--verify", "HEAD"], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _selection_summary(payload: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in payload["projects"]:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    return {"project_count": payload["project_count"], "known_blacklist_count": payload["known_blacklist_count"], "strata": counts}


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())

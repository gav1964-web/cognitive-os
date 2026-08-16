"""Freeze and clone a reproducible GitHub blind corpus."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "github_blind_corpus_strata.json"
API_URL = "https://api.github.com/search/repositories"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("select", "clone"))
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
    else:
        report = clone_corpus(corpus, force=args.force)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def select_corpus(root: Path, corpus: Path, iteration: int, policy_path: Path) -> dict[str, Any]:
    selection_path = corpus / "selection.json"
    if selection_path.exists():
        raise RuntimeError("selection is already frozen; choose a new corpus directory")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    blacklist = known_projects(root / "artifacts")
    selected: list[dict[str, Any]] = []
    claimed = set(blacklist)
    for stratum in policy["strata"]:
        count = int(policy["projects_per_stratum"])
        print(f"searching stratum={stratum['id']} needed={count}", file=sys.stderr, flush=True)
        candidates = _search_stratum(stratum, policy, excluded=claimed, needed=count)
        rows = [row for row in candidates if row["full_name"].lower() not in claimed and _eligible(row, policy)]
        if len(rows) < count:
            raise RuntimeError(f"not enough unseen projects for {stratum['id']}: {len(rows)} < {count}")
        for row in rows[:count]:
            row["stratum"] = str(stratum["id"])
            selected.append(row)
            claimed.add(row["full_name"].lower())
        print(f"selected stratum={stratum['id']} count={count}", file=sys.stderr, flush=True)
    corpus.mkdir(parents=True, exist_ok=False)
    payload = {
        "artifact_type": "GitHubBlindCorpusSelection",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection_frozen": True,
        "iteration": iteration,
        "known_blacklist_count": len(blacklist),
        "project_count": len(selected),
        "policy": policy,
        "projects": selected,
    }
    selection_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "selection_path": selection_path.as_posix(), **_selection_summary(payload)}


def clone_corpus(corpus: Path, *, force: bool = False) -> dict[str, Any]:
    selection_path = corpus / "selection.json"
    if not selection_path.exists():
        raise RuntimeError("selection.json must be frozen before clone phase")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("selection_frozen") is not True:
        raise RuntimeError("selection is not frozen")
    source_dir = corpus / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    rows = [_clone_one(source_dir, project, force=force) for project in selection["projects"]]
    status = "ok" if all(row["status"] == "ok" for row in rows) else "failed"
    report = {
        "artifact_type": "GitHubBlindCorpusCloneReport",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection_path": selection_path.as_posix(),
        "project_count": len(rows),
        "cloned": sum(row["status"] == "ok" for row in rows),
        "failed": sum(row["status"] != "ok" for row in rows),
        "results": rows,
    }
    (corpus / "clone_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def known_projects(artifacts: Path) -> set[str]:
    known: set[str] = set()
    for child in artifacts.iterdir() if artifacts.is_dir() else []:
        selection = child / "selection.json"
        if not selection.is_file():
            continue
        try:
            payload = json.loads(selection.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        known.update(str(row.get("full_name") or "").lower() for row in payload.get("projects", []) if row.get("full_name"))
    field_trials = artifacts / "field_trials"
    for report in field_trials.glob("role_foundation_min_field_trial_*.json") if field_trials.is_dir() else []:
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for case in payload.get("cases", []):
            project = str(case.get("project") or "")
            if "__" in project:
                owner, repo = project.split("__", 1)
                if owner and repo:
                    known.add(f"{owner}/{repo}".lower())
    return known


def _search_stratum(
    stratum: dict[str, Any],
    policy: dict[str, Any],
    *,
    excluded: set[str] | None = None,
    needed: int = 0,
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    excluded = excluded or set()
    qualifiers = (
        f"language:Python stars:>={int(policy['minimum_stars'])} "
        f"size:<={int(policy['maximum_size_kb'])} archived:false fork:false"
    )
    max_pages = int(policy.get("maximum_search_pages") or 3) if needed else 1
    for page in range(1, max_pages + 1):
        for query in stratum["queries"]:
            fields = {
                "q": f"{query} {qualifiers}", "sort": "stars", "order": "desc",
                "per_page": "100", "page": str(page),
            }
            payload = _search_page(fields)
            for item in payload.get("items", []):
                row = _project_row(item)
                by_name.setdefault(row["full_name"].lower(), row)
            eligible = [row for key, row in by_name.items() if key not in excluded and _eligible(row, policy)]
            print(
                f"search progress stratum={stratum.get('id', 'unknown')} page={page} eligible={len(eligible)}",
                file=sys.stderr,
                flush=True,
            )
            if needed and len(eligible) >= needed:
                return sorted(by_name.values(), key=lambda row: (-row["stars"], row["full_name"].lower()))
    return sorted(by_name.values(), key=lambda row: (-row["stars"], row["full_name"].lower()))


def _search_page(fields: dict[str, str]) -> dict[str, Any]:
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return _search_with_gh(fields)
    try:
        return _search_with_urllib(urllib.parse.urlencode(fields))
    except HTTPError as exc:
        if exc.code == 403 and shutil.which("gh"):
            return _search_with_gh(fields)
        raise


def _search_with_urllib(params: str) -> dict[str, Any]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "cognitive-os-blind-corpus"}
        request = urllib.request.Request(f"{API_URL}?{params}", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)


def _search_with_gh(fields: dict[str, str]) -> dict[str, Any]:
    command = ["gh", "api", "--method", "GET", "search/repositories"]
    for key, value in fields.items():
        command.extend(["-f", f"{key}={value}"])
    for attempt in range(2):
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if attempt == 0 and "API rate limit exceeded" in result.stderr:
            time.sleep(65)
            continue
        raise RuntimeError("authenticated GitHub search failed: " + result.stderr[-500:])
    raise RuntimeError("authenticated GitHub search retry exhausted")


def _project_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "full_name": str(item["full_name"]),
        "clone_url": str(item["clone_url"]),
        "stars": int(item.get("stargazers_count") or 0),
        "size_kb": int(item.get("size") or 0),
        "default_branch": str(item.get("default_branch") or ""),
        "html_url": str(item.get("html_url") or ""),
        "description": str(item.get("description") or ""),
        "topics": sorted(str(topic) for topic in item.get("topics", [])),
    }


def _eligible(row: dict[str, Any], policy: dict[str, Any]) -> bool:
    name = row["full_name"].lower().replace("-", "_")
    description = row["description"].lower()
    if any(token.replace("-", "_") in name for token in policy.get("excluded_name_tokens", [])):
        return False
    if any(token in description for token in policy.get("excluded_description_tokens", [])):
        return False
    signals = " ".join([name, description, *row.get("topics", [])])
    required = policy.get("production_signal_tokens", [])
    return not required or any(token in signals for token in required)


def _clone_one(source_dir: Path, project: dict[str, Any], *, force: bool) -> dict[str, Any]:
    destination = source_dir / str(project["full_name"]).replace("/", "__")
    if destination.exists() and _checkout_ready(destination):
        return {"full_name": project["full_name"], "status": "ok", "path": destination.as_posix(), "reused": True}
    if destination.exists():
        recovery = _export_compatible_tree(destination) if force else None
        if recovery:
            return {"full_name": project["full_name"], "status": "ok", "path": destination.as_posix(), **recovery}
        raise RuntimeError(f"refusing to remove existing clone automatically: {destination}")
    result = subprocess.run(
        ["git", "-c", "core.longpaths=true", "clone", "--depth", "1", "--filter=blob:none", str(project["clone_url"]), str(destination)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    row = {
        "full_name": project["full_name"],
        "status": "ok" if result.returncode == 0 else "clone_failed",
        "path": destination.as_posix(),
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-800:],
    }
    if result.returncode != 0:
        recovery = _export_compatible_tree(destination)
        if recovery:
            row.update(status="ok", **recovery)
    return row


def _export_compatible_tree(destination: Path) -> dict[str, Any] | None:
    safe = f"safe.directory={destination.as_posix()}"
    listing = subprocess.run(
        ["git", "-c", safe, "-C", str(destination), "ls-tree", "-rz", "--name-only", "HEAD"],
        capture_output=True,
        timeout=30,
    )
    if listing.returncode != 0:
        return None
    exported = 0
    omitted: list[str] = []
    for raw_path in listing.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="replace")
        if not _windows_compatible_path(relative):
            omitted.append(relative)
            continue
        blob = subprocess.run(
            ["git", "-c", safe, "-C", str(destination), "show", f"HEAD:{relative}"],
            capture_output=True,
            timeout=30,
        )
        if blob.returncode != 0:
            omitted.append(relative)
            continue
        target = destination / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob.stdout)
        exported += 1
    if not exported:
        return None
    return {
        "checkout_recovery": "compatible_tree_export",
        "exported_files": exported,
        "omitted_paths": omitted,
    }


def _windows_compatible_path(relative: str) -> bool:
    invalid = set('<>:"|?*')
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in relative.replace("\\", "/").split("/"):
        stem = part.split(".", 1)[0].upper()
        if not part or part.endswith((" ", ".")) or stem in reserved:
            return False
        if any(char in invalid or ord(char) < 32 for char in part):
            return False
    return True


def _checkout_ready(destination: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(destination), "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _selection_summary(payload: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in payload["projects"]:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    return {"project_count": payload["project_count"], "known_blacklist_count": payload["known_blacklist_count"], "strata": counts}


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())

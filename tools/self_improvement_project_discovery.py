"""External project discovery adapter for Cognitive OS hypothesis validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.gitlab_blind_corpus import (
    _clone_one,
    _repo_key,
    _search_stratum,
    _unseen,
    known_projects,
)


def gitlab_holdout_discoverer(root: Path) -> Callable[[dict[str, Any]], list[Path]]:
    return lambda plan: discover_gitlab_holdouts(root, plan)


def discover_gitlab_holdouts(root: Path, plan: dict[str, Any]) -> list[Path]:
    if plan.get("provider") != "gitlab":
        raise ValueError(f"unsupported holdout provider: {plan.get('provider')}")
    directory = root / "artifacts" / "hypothesis_holdouts" / str(plan["hypothesis_id"])
    selection_path = directory / "selection.json"
    if selection_path.is_file():
        projects = list(json.loads(selection_path.read_text(encoding="utf-8")).get("projects") or [])
    else:
        projects = _select_projects(root, plan)
        directory.mkdir(parents=True, exist_ok=False)
        selection_path.write_text(json.dumps({
            "artifact_type": "HypothesisHoldoutSelection",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hypothesis_id": plan["hypothesis_id"],
            "portable_signature": plan["portable_signature"],
            "selection_frozen": True,
            "projects": projects,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_dir = directory / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    results = [_clone_one(source_dir, project, force=False) for project in projects]
    report = {
        "artifact_type": "HypothesisHoldoutCloneReport",
        "status": "ok" if all(row["status"] == "ok" for row in results) else "partial",
        "hypothesis_id": plan["hypothesis_id"],
        "results": results,
    }
    (directory / "clone_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return [Path(row["path"]) for row in results if row["status"] == "ok"]


def _select_projects(root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    policy = json.loads((root / "config" / "gitlab_blind_corpus_strata.json").read_text(encoding="utf-8"))
    policy.update({
        "maximum_search_pages": int(plan["maximum_search_pages"]),
        "search_page_batch_size": 1,
        "search_workers": min(4, int(policy.get("search_workers") or 4)),
    })
    known_names, known_repos = known_projects(root / "artifacts")
    known_repos.update(
        _repo_key(str(name).rsplit("__", 1)[-1])
        for name in plan.get("excluded_projects") or []
    )
    needed = int(plan["maximum_projects"])
    candidates = _search_stratum(
        {"id": plan["hypothesis_id"], "queries": list(plan["queries"])}, policy,
        excluded_names=known_names, excluded_repos=known_repos, needed=needed,
    )
    selected = []
    for row in candidates:
        if not _unseen(row, known_names, known_repos):
            continue
        selected.append(row)
        known_names.add(str(row["full_name"]).lower())
        known_repos.add(_repo_key(str(row["full_name"])))
        if len(selected) >= needed:
            break
    return selected

"""Provider-chain project discovery for Cognitive OS hypothesis validation."""

from __future__ import annotations

import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from runtime.hypothesis_structural_screen import screen_projects
from runtime.self_improvement_target_alignment import recovery_targets, retrieval_targets
from tools.github_blind_corpus import _clone_one as _clone_github
from tools.github_blind_corpus import _eligible as _eligible_github
from tools.github_blind_corpus import _search_stratum as _search_github
from tools.gitlab_blind_corpus import _clone_one as _clone_gitlab
from tools.gitlab_blind_corpus import _eligible as _eligible_gitlab
from tools.gitlab_blind_corpus import _repo_key, _search_stratum as _search_gitlab
from tools.gitlab_blind_corpus import known_projects


def holdout_discoverer(root: Path) -> Callable[[dict[str, Any]], list[Path]]:
    return lambda plan: discover_holdouts(root, plan)


def gitlab_holdout_discoverer(root: Path) -> Callable[[dict[str, Any]], list[Path]]:
    """Compatibility facade for callers that explicitly require GitLab only."""
    return lambda plan: discover_holdouts(root, {**plan, "providers": ["gitlab"]})


def discover_gitlab_holdouts(root: Path, plan: dict[str, Any]) -> list[Path]:
    return discover_holdouts(root, {**plan, "providers": ["gitlab"]})


def discover_holdouts(root: Path, plan: dict[str, Any]) -> list[Path]:
    directory = _holdout_directory(root, plan)
    selection_path = directory / "selection.json"
    if selection_path.is_file():
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        projects = list(selection.get("projects") or [])
        attempts = list(selection.get("provider_attempts") or [])
    else:
        projects, attempts = _select_projects(root, plan)
        if attempts and all(row.get("status") == "failed" for row in attempts):
            raise RuntimeError(f"holdout provider chain unavailable: {attempts}")
        directory.mkdir(parents=True, exist_ok=False)
        selection_path.write_text(json.dumps({
            "artifact_type": "HypothesisHoldoutSelection",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hypothesis_id": plan["hypothesis_id"],
            "portable_signature": plan["portable_signature"],
            "selection_frozen": True,
            "provider_attempts": attempts,
            "projects": projects,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_dir = directory / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    workers = min(max(1, int(plan.get("clone_workers") or 1)), 8, max(1, len(projects)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda project: _clone(source_dir, project), projects))
    report = {
        "artifact_type": "HypothesisHoldoutCloneReport",
        "status": "ok" if all(row["status"] == "ok" for row in results) else "partial",
        "hypothesis_id": plan["hypothesis_id"], "provider_attempts": attempts,
        "results": results,
    }
    (directory / "clone_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    cloned = [Path(row["path"]) for row in results if row["status"] == "ok"]
    return _structural_shortlist(directory, cloned, plan)


def _holdout_directory(root: Path, plan: dict[str, Any]) -> Path:
    name = str(plan["hypothesis_id"])
    if "search_page_start" in plan:
        window = json.dumps({
            "plan_version": str(plan.get("plan_version") or ""),
            "semantic_context": list(plan.get("semantic_context") or []),
            "queries": list(plan.get("queries") or []),
            "page_start": int(plan.get("search_page_start") or 1),
            "page_end": int(plan.get("query_page_end") or 0),
        }, ensure_ascii=True, sort_keys=True)
        name = f"{name}_w{hashlib.sha256(window.encode()).hexdigest()[:8]}"
    return root / "artifacts" / "hypothesis_holdouts" / name


def _select_projects(root: Path, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    known_names, known_repos = known_projects(root / "artifacts")
    known_repos.update(
        _repo_key(str(name).rsplit("__", 1)[-1])
        for name in plan.get("excluded_projects") or []
    )
    selected: list[dict[str, Any]] = []
    attempts = []
    maximum = int(plan.get("candidate_pool_projects") or plan["maximum_projects"])
    for provider in plan.get("providers") or ["gitlab"]:
        needed = maximum - len(selected)
        if needed <= 0:
            break
        try:
            candidates = _provider_candidates(root, plan, str(provider), known_names, known_repos, needed)
            accepted = _claim_candidates(candidates, str(provider), known_names, known_repos, needed)
            selected.extend(accepted)
            attempts.append({"provider": provider, "status": "ok", "selected": len(accepted)})
        except Exception as exc:
            attempts.append({
                "provider": provider, "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            })
    return selected, attempts


def _provider_candidates(
    root: Path, plan: dict[str, Any], provider: str,
    known_names: set[str], known_repos: set[str], needed: int,
) -> list[dict[str, Any]]:
    if provider == "gitlab":
        policy = _policy(root, "gitlab_blind_corpus_strata.json", plan)
        candidates = _search_gitlab(
            _stratum(plan, provider), policy, excluded_names=known_names,
            excluded_repos=known_repos, needed=needed,
        )
        return [row for row in candidates if _eligible_gitlab(row, policy)]
    if provider == "github":
        policy = _policy(root, "github_blind_corpus_strata.json", plan)
        candidates = _search_github(
            _stratum(plan, provider), policy, excluded={name.lower() for name in known_names}, needed=needed,
        )
        return [row for row in candidates if _eligible_github(row, policy)]
    raise ValueError(f"unsupported holdout provider: {provider}")


def _policy(root: Path, name: str, plan: dict[str, Any]) -> dict[str, Any]:
    policy = json.loads((root / "config" / name).read_text(encoding="utf-8"))
    provider = "gitlab" if name.startswith("gitlab") else "github"
    overrides = dict(dict(plan.get("provider_policy_overrides") or {}).get(provider) or {})
    for key in ("minimum_stars", "maximum_size_kb"):
        if key in overrides:
            policy[key] = int(overrides[key])
    policy["maximum_search_pages"] = int(plan["maximum_search_pages"])
    policy["search_page_start"] = int(plan.get("search_page_start") or 1)
    if name.startswith("gitlab"):
        policy.update({
            "search_page_batch_size": 1,
            "search_workers": min(4, int(policy.get("search_workers") or 4)),
        })
    return policy


def _stratum(plan: dict[str, Any], provider: str = "github") -> dict[str, Any]:
    return {"id": plan["hypothesis_id"], "queries": _provider_queries(plan, provider)}


def _provider_queries(plan: dict[str, Any], provider: str) -> list[str]:
    result = []
    for value in plan.get("queries") or []:
        query = str(value)
        if provider == "gitlab":
            if query.startswith("topic:"):
                query = query[6:].replace("-", " ")
            query = query.split(" in:", 1)[0]
        if query and query not in result:
            result.append(query)
    return result


def _claim_candidates(
    candidates: list[dict[str, Any]], provider: str, known_names: set[str],
    known_repos: set[str], needed: int,
) -> list[dict[str, Any]]:
    accepted = []
    for candidate in candidates:
        name = str(candidate["full_name"])
        repo = _repo_key(name)
        if name.lower() in known_names or repo in known_repos:
            continue
        accepted.append({**candidate, "provider": provider})
        known_names.add(name.lower()); known_repos.add(repo)
        if len(accepted) >= needed:
            break
    return accepted


def _clone(source_dir: Path, project: dict[str, Any]) -> dict[str, Any]:
    provider = str(project.get("provider") or "gitlab")
    clone = _clone_gitlab if provider == "gitlab" else _clone_github
    try:
        return {"provider": provider, **clone(source_dir, project, force=False)}
    except Exception as exc:
        return {
            "provider": provider, "full_name": project.get("full_name"),
            "status": "clone_failed", "error": f"{type(exc).__name__}: {exc}",
        }


def _structural_shortlist(
    directory: Path, projects: list[Path], plan: dict[str, Any]
) -> list[Path]:
    policy = dict(plan.get("structural_prescreen") or {})
    projects = _resource_screen(directory, projects, policy)
    if not policy.get("enabled"):
        return projects
    normalization = dict(plan.get("signature_normalization") or {})
    policy["output_basis_families"] = dict(
        normalization.get("output_basis_families") or {}
    )
    policy["recovery_contract"] = dict(plan.get("recovery_contract") or {})
    policy["semantic_context"] = list(plan.get("semantic_context") or [])
    report_path = directory / "structural_screen.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = screen_projects(projects, str(plan["portable_signature"]), policy)
        report.update({
            "hypothesis_id": plan["hypothesis_id"],
            "retrieval_evidence_only": True,
            "screening_frozen": True,
        })
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    by_name = {project.name: project for project in projects}
    plan["retrieval_targets"] = retrieval_targets(report)
    plan["recovery_targets"] = recovery_targets(report)
    return [
        by_name[name] for name in report["selected_projects"]
        if name in by_name
    ]


def _resource_screen(
    directory: Path, projects: list[Path], policy: dict[str, Any]
) -> list[Path]:
    maximum = max(
        1024,
        int(
            policy.get("maximum_project_python_file_bytes")
            or int(policy.get("maximum_file_bytes") or 500_000) * 2
        ),
    )
    accepted = []
    rejected = []
    for project in projects:
        oversized = []
        try:
            python_files = project.rglob("*.py")
            for path in python_files:
                size = path.stat().st_size
                if size > maximum:
                    oversized.append({
                        "path": path.relative_to(project).as_posix(),
                        "size_bytes": size,
                    })
        except OSError as exc:
            rejected.append({
                "project": project.name,
                "reason": "resource_scan_failed",
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        if oversized:
            rejected.append({
                "project": project.name,
                "reason": "python_file_resource_budget_exceeded",
                "files": oversized[:8],
            })
        else:
            accepted.append(project)
    report = {
        "artifact_type": "HypothesisHoldoutResourceScreen",
        "maximum_project_python_file_bytes": maximum,
        "candidate_project_count": len(projects),
        "accepted_project_count": len(accepted),
        "rejected": rejected,
    }
    (directory / "resource_screen.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return accepted

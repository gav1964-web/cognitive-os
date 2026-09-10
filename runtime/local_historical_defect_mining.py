"""Mine sealed historical defect candidates from untouched local Git corpora."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .local_historical_defect_evidence import (
    canonical as _canonical,
    evidence_digest as _digest,
    file_digest as _file_digest,
    inside as _inside,
    is_relative_to as _is_relative_to,
    write_manifests as _write_manifests,
)
from .self_development_challenge_evidence import (
    bounded_project_text,
    declared_script_entrypoints,
    exposed_projects,
    name_signal_matches,
    signal_score,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "local_historical_defect_mining.json"
SCHEMA_VERSION = "local_historical_defect_mining.v1"
TARGET_TYPES = ("cli_local_tool", "library_pure_transform")


from cognitive_replay.git import HistoricalDefectMiningError


@lru_cache(maxsize=1)
def load_historical_mining_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("status") != "active":
        raise HistoricalDefectMiningError("historical mining policy is not active")
    if tuple(payload.get("target_project_types") or ()) != TARGET_TYPES:
        raise HistoricalDefectMiningError("historical mining target types are invalid")
    positive = (
        "minimum_candidates_per_type", "scan_limit", "max_commits_per_project",
        "max_changed_files", "max_production_python_files", "max_test_python_files",
    )
    if any(int(payload.get(name) or 0) < 1 for name in positive):
        raise HistoricalDefectMiningError("historical mining limits must be positive")
    if not all(payload.get(name) for name in (
        "prospective_evidence_glob", "native_failure_evidence_glob",
        "historical_selection_evidence_glob",
    )):
        raise HistoricalDefectMiningError("historical mining exposure evidence is incomplete")
    invariants = dict(payload.get("invariants") or {})
    required_true = (
        "local_corpus_first", "untouched_projects_only", "owner_independent",
        "production_and_test_delta_required", "baseline_frozen_before_execution",
        "fix_oracle_separated",
    )
    if not all(invariants.get(name) is True for name in required_true):
        raise HistoricalDefectMiningError("historical mining invariants are incomplete")
    if invariants.get("source_apply") is not False or invariants.get("automatic_promotion") is not False:
        raise HistoricalDefectMiningError("historical mining mutation boundary is unsafe")
    return payload


def mine_historical_defect_candidates(
    *, root: Path, policy: dict[str, Any] | None = None, write: bool = False,
    project_types: tuple[str, ...] = TARGET_TYPES,
) -> dict[str, Any]:
    if not project_types or len(set(project_types)) != len(project_types) or set(project_types) - set(TARGET_TYPES):
        raise HistoricalDefectMiningError("historical mining project types are invalid")
    base = root.resolve()
    rules = policy or load_historical_mining_policy(
        str(base / "config" / "local_historical_defect_mining.json")
    )
    index_path = _inside(base, str(rules["corpus_index"]))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema_version") != "self_development_corpus_eligibility_index.v1":
        raise HistoricalDefectMiningError("corpus index schema mismatch")
    exposed = _exposure_set(base, rules)
    reserved = {
        _canonical(str(row.get("canonical_project") or row.get("project") or ""))
        for name in ("acquisition", "holdout") for row in index.get(name) or []
    }
    rows = [
        dict(row) for row in index.get("projects") or []
        if row.get("exposure") == "untouched"
        and _canonical(str(row.get("canonical_project") or row.get("project") or "")) not in exposed
        and _canonical(str(row.get("canonical_project") or row.get("project") or "")) not in reserved
    ]
    ordered = sorted(rows, key=lambda row: _split_key(row, str(rules["split_seed"])))
    candidates: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGET_TYPES}
    shallow_sources: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGET_TYPES}
    classified_snapshots = {name: 0 for name in TARGET_TYPES}
    rejection_counts = {
        "git_metadata_missing": 0, "git_snapshot_unavailable": 0,
        "dirty_worktree": 0, "origin_missing": 0, "shallow_history": 0,
        "project_type_unqualified": 0, "qualifying_fix_commit_missing": 0,
        "project_type_not_requested": 0,
    }
    scanned = git_repositories = shallow_repositories = history_capable = commits_considered = 0
    required = int(rules["minimum_candidates_per_type"])
    for row in ordered[: int(rules["scan_limit"])]:
        scanned += 1
        project = _inside(base, str(row.get("project_root") or ""))
        if not project.is_dir() or not (project / ".git").exists():
            rejection_counts["git_metadata_missing"] += 1
            continue
        snapshot = _git_snapshot(project)
        if not snapshot:
            rejection_counts["git_snapshot_unavailable"] += 1
            continue
        git_repositories += 1
        if snapshot["status"]:
            rejection_counts["dirty_worktree"] += 1
            continue
        if not snapshot["origin"]:
            rejection_counts["origin_missing"] += 1
            continue
        history_missing = int(snapshot.get("history_count") or 0) < 2
        if snapshot.get("shallow") == "true":
            shallow_repositories += 1
        project_type, identity = _classify(project, rules)
        if not project_type:
            rejection_counts["project_type_unqualified"] += 1
            continue
        if project_type not in project_types:
            rejection_counts["project_type_not_requested"] += 1
            continue
        classified_snapshots[project_type] += 1
        if history_missing:
            rejection_counts["shallow_history"] += 1
            shallow_sources[project_type].append(
                _shallow_source(row, snapshot, project_type, identity)
            )
            continue
        history_capable += 1
        found, considered = _project_candidate(project, row, snapshot, project_type, identity, rules)
        commits_considered += considered
        if found:
            candidates[project_type].append(found)
        else:
            rejection_counts["qualifying_fix_commit_missing"] += 1
        if all(len(_take_independent(candidates[name], required)) >= required for name in TARGET_TYPES):
            break
    selected = {
        name: _take_independent(candidates[name], required)
        for name in TARGET_TYPES
    }
    suggested_sources = {
        name: _take_independent(shallow_sources[name], required * 3)
        for name in TARGET_TYPES
    }
    public_cases = [row["public"] for name in TARGET_TYPES for row in selected[name]]
    oracle_cases = [row["oracle"] for name in TARGET_TYPES for row in selected[name]]
    counts = {name: len(selected[name]) for name in TARGET_TYPES}
    checks = {
        "source_index_local": _is_relative_to(index_path, base),
        "source_index_sufficient": index.get("status") == "local_corpus_sufficient",
        "selected_untouched": all(row["exposure"] == "untouched" for row in public_cases),
        "owner_independent": all(_independent(selected[name], "owner") for name in TARGET_TYPES),
        "content_independent": all(_independent(selected[name], "content_fingerprint") for name in TARGET_TYPES),
        "minimum_candidates_met": all(counts[name] >= required for name in TARGET_TYPES),
        "production_and_test_delta": all(
            row["production_files"] and row["test_files"] for row in oracle_cases
        ),
        "fix_oracle_separated": all("fix_revision" not in row for row in public_cases),
        "no_source_apply": True,
        "no_automatic_promotion": True,
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    public = {
        "artifact_type": "LocalHistoricalDefectPublicManifest",
        "schema_version": "local_historical_defect_public_manifest.v1",
        "status": "ready" if all(checks.values()) else "shortage",
        "generated_at": generated_at,
        "source_index": str(rules["corpus_index"]),
        "source_index_sha256": _file_digest(index_path),
        "request": {"project_types": list(project_types), "scan_limit": int(rules["scan_limit"])},
        "summary": {
            "projects_scanned": scanned, "git_repositories": git_repositories,
            "shallow_git_repositories": shallow_repositories,
            "history_capable_git_repositories": history_capable,
            "classified_snapshot_counts": classified_snapshots,
            "commits_considered": commits_considered, "candidate_counts": counts,
            "rejection_counts": rejection_counts,
        },
        "cases": public_cases,
        "network_fallback": {
            "required": not checks["minimum_candidates_met"],
            "reason": "local_git_histories_are_shallow",
            "suggested_sources": suggested_sources,
            "source_apply": False,
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "oracle_disclosure": "separate_file_not_for_role_input",
        "safety": {"source_apply": False, "automatic_promotion": False},
    }
    public["manifest_digest"] = _digest(public)
    oracle = {
        "artifact_type": "LocalHistoricalDefectOracle",
        "schema_version": "local_historical_defect_oracle.v1",
        "status": "sealed",
        "generated_at": generated_at,
        "public_manifest_digest": public["manifest_digest"],
        "cases": oracle_cases,
        "disclosure_policy": "withhold_until_role_outcome_is_frozen",
    }
    oracle["oracle_digest"] = _digest(oracle)
    paths = _write_manifests(base, public, oracle) if write else {}
    return {"public_manifest": public, "oracle_manifest": oracle, "paths": paths}


def _shallow_source(
    row: dict[str, Any], snapshot: dict[str, str], project_type: str, identity: str,
) -> dict[str, Any]:
    return {
        "project": row.get("project"),
        "canonical_project": row.get("canonical_project"),
        "project_stratum": project_type,
        "classification_evidence": identity,
        "owner": row.get("owner"),
        "project_root": row.get("project_root"),
        "source_url": snapshot.get("origin"),
        "snapshot_revision": snapshot.get("revision"),
        "content_fingerprint": str(row.get("content_fingerprint") or ""),
        "exposure": "untouched",
    }


def _project_candidate(
    project: Path, row: dict[str, Any], snapshot: dict[str, str], project_type: str,
    identity: str, rules: dict[str, Any],
) -> tuple[dict[str, Any] | None, int]:
    output = _git(project, [
        "log", "--no-merges", f"-n{int(rules['max_commits_per_project'])}",
        "--format=%H%x1f%P%x1f%s",
    ])
    considered = 0
    pattern = _token_pattern([str(value) for value in rules["fix_message_tokens"]])
    for line in output.splitlines():
        fields = line.split("\x1f", 2)
        if len(fields) != 3 or not pattern.search(fields[2]):
            continue
        fix_revision, parents, subject = fields
        parent_values = parents.split()
        if len(parent_values) != 1:
            continue
        considered += 1
        changes = _changed_files(project, fix_revision)
        production = [path for _status, path in changes if _production_python(path)]
        test_support = [path for _status, path in changes if _test_support(path)]
        test_entries = [path for path in test_support if path.endswith(".py")]
        if (
            not production or not test_entries or len(changes) > int(rules["max_changed_files"])
            or len(production) > int(rules["max_production_python_files"])
            or len(test_support) > int(rules["max_test_python_files"])
        ):
            continue
        baseline = parent_values[0]
        candidate_id = hashlib.sha256(
            f"{snapshot['origin']}:{baseline}:{fix_revision}".encode("utf-8")
        ).hexdigest()[:20]
        owner = str(row.get("owner") or _canonical(project.name).split("__", 1)[0])
        public = {
            "candidate_id": candidate_id,
            "project": row.get("project"), "canonical_project": row.get("canonical_project"),
            "project_stratum": project_type, "classification_evidence": identity,
            "owner": owner, "project_root": row.get("project_root"),
            "source_url": snapshot["origin"], "baseline_revision": baseline,
            "candidate_test_files": test_entries,
            "candidate_test_support_files": test_support,
            "content_fingerprint": str(row.get("content_fingerprint") or ""),
            "exposure": "untouched", "oracle_ref": candidate_id,
        }
        oracle = {
            "candidate_id": candidate_id, "fix_revision": fix_revision,
            "commit_subject": subject, "production_files": production,
            "test_files": test_support, "test_entry_files": test_entries,
            "production_patch_sha256": _patch_digest(project, baseline, fix_revision, production),
            "test_patch_sha256": _patch_digest(project, baseline, fix_revision, test_support),
        }
        return {"public": public, "oracle": oracle, "owner": owner,
                "content_fingerprint": public["content_fingerprint"]}, considered
    return None, considered


def _classify(project: Path, rules: dict[str, Any]) -> tuple[str, str]:
    text = bounded_project_text(project)
    excluded_cli = [str(value).lower() for value in rules["excluded_cli_signals"]]
    if declared_script_entrypoints(project) and not _token_pattern(excluded_cli).search(text):
        return "cli_local_tool", "declared_script_entrypoint"
    excluded = [str(value).lower() for value in rules["excluded_library_signals"]]
    score = signal_score(text, [str(value) for value in dict(rules["signals"])["library_pure_transform"]])
    required_names = [str(value) for value in rules["required_library_name_signals"]]
    name_bound = any(name_signal_matches(project.name, value) for value in required_names)
    if score >= 2 and name_bound and not _token_pattern(excluded).search(text):
        return "library_pure_transform", "token_bound_name_and_transform_signals"
    return "", "unqualified_project_type"


from cognitive_replay.git import _git_snapshot


from cognitive_replay.git import _git


def _changed_files(project: Path, revision: str) -> list[tuple[str, str]]:
    try:
        output = _git(project, [
            "diff-tree", "--no-commit-id", "--name-status", "-r", "--find-renames", revision,
        ])
    except HistoricalDefectMiningError:
        return []
    rows = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            rows.append((fields[0], fields[-1].replace("\\", "/")))
    return rows


def _patch_digest(project: Path, baseline: str, fix: str, paths: list[str]) -> str:
    patch = _git(project, ["diff", "--no-ext-diff", baseline, fix, "--", *paths])
    return "sha256:" + hashlib.sha256(patch.encode("utf-8")).hexdigest()


def _test_support(path: str) -> bool:
    parts = path.lower().split("/")
    name = parts[-1]
    return "tests" in parts or "test" in parts or name.startswith("test_")


def _production_python(path: str) -> bool:
    return path.endswith(".py") and not _test_support(path)


def _take_independent(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    result, owners, fingerprints = [], set(), set()
    for row in rows:
        if row["owner"] in owners or row["content_fingerprint"] in fingerprints:
            continue
        result.append(row); owners.add(row["owner"]); fingerprints.add(row["content_fingerprint"])
        if len(result) == count:
            break
    return result


def _independent(rows: list[dict[str, Any]], key: str) -> bool:
    values = [row[key] for row in rows]
    return len(values) == len(set(values)) and all(values)


def _exposure_set(root: Path, rules: dict[str, Any]) -> set[str]:
    values = exposed_projects(root, str(rules["prospective_evidence_glob"]))
    values |= exposed_projects(root, str(rules["native_failure_evidence_glob"]))
    values |= exposed_projects(root, str(rules["historical_selection_evidence_glob"]))
    return {_canonical(value) for value in values}


def _token_pattern(values: list[str]) -> re.Pattern[str]:
    body = "|".join(re.escape(value.lower()) for value in values if value) or r"(?!)"
    return re.compile(rf"(?<![a-z0-9])(?:{body})(?:ed|es|ing|s)?(?![a-z0-9])", re.IGNORECASE)


def _split_key(row: dict[str, Any], seed: str) -> str:
    value = f"{seed}:{row.get('canonical_project')}:{row.get('content_fingerprint')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

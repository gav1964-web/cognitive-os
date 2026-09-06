"""Plan and run prospective challenges on untouched local projects."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .project_development import run_project_development
from .self_development_collector import collect_project_development_report
from .self_development_experiment_queue import build_self_development_experiment_queue
from .self_development_prospective_detection import run_prospective_detection


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_challenge_campaign.json"


class ChallengeCampaignError(ValueError):
    """Raised when challenge selection would violate evidence boundaries."""


@lru_cache(maxsize=1)
def load_challenge_campaign_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_challenge_campaign.v1":
        raise ChallengeCampaignError("challenge campaign policy schema mismatch")
    if payload.get("status") != "active" or len(payload.get("target_project_types") or []) != 2:
        raise ChallengeCampaignError("challenge campaign scope is incomplete")
    if min(int(payload.get("acquisition_per_type") or 0), int(payload.get("holdout_per_type") or 0)) < 2:
        raise ChallengeCampaignError("challenge campaign requires independent splits")
    invariants = dict(payload.get("invariants") or {})
    required = (
        "untouched_only", "owner_independent", "content_independent",
        "holdout_frozen_before_execution", "external_acquisition_only_after_local_shortage",
    )
    if not all(invariants.get(name) is True for name in required):
        raise ChallengeCampaignError("challenge campaign invariants are incomplete")
    if any(invariants.get(name) is not False for name in (
        "holdout_consumed", "source_apply", "promotion_applied"
    )):
        raise ChallengeCampaignError("challenge campaign mutation boundary is unsafe")
    return payload


def build_challenge_manifest(
    *, root: Path, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_challenge_campaign_policy(
        str(base / "config" / "self_development_challenge_campaign.json")
    )
    index = _read_inside(base, str(rules["corpus_index"]))
    dynamically_exposed = _exposed_projects(base, str(rules["prospective_evidence_glob"]))
    reserved = {
        str(row.get("canonical_project"))
        for key in ("acquisition", "holdout")
        for row in index.get(key) or []
    }
    rows = [
        dict(row) for row in index.get("projects") or []
        if row.get("exposure") == "untouched"
        and row.get("canonical_project") not in reserved
        and str(row.get("project") or "").lower() not in dynamically_exposed
        and int(row.get("python_files_sampled") or 0) >= 2
        and str(row.get("content_fingerprint") or "") != hashlib.sha256(b"").hexdigest()
        and (base / str(row.get("project_root") or "")).is_dir()
    ]
    ordered = sorted(rows, key=lambda row: _split_key(row, str(rules["split_seed"])))
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    for row in ordered[: int(rules["scan_limit"])]:
        scanned += 1
        root_path = (base / str(row["project_root"])).resolve()
        text = _bounded_project_text(root_path)
        scores = {
            project_type: _signal_score(text, list(dict(rules["signals"])[project_type]))
            for project_type in rules["target_project_types"]
        }
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        selected_type = ranked[0][0]
        name = str(row.get("project") or "").lower()
        required_name = list(dict(rules["required_name_signals"])[selected_type])
        excluded = list(dict(rules["excluded_signals"])[selected_type])
        if (
            ranked[0][1] < 2
            or ranked[0][1] == ranked[1][1]
            or not any(_name_signal_matches(name, signal) for signal in required_name)
            or any(signal.lower() in text for signal in excluded)
        ):
            continue
        candidates[selected_type].append({
            "project": row.get("project"),
            "canonical_project": row.get("canonical_project"),
            "project_root": row.get("project_root"),
            "owner": row.get("owner"),
            "content_digest": "sha256:" + str(row.get("content_fingerprint")),
            "expected_project_type": selected_type,
            "signal_scores": scores,
        })
    splits, shortages = [], {}
    for project_type in rules["target_project_types"]:
        needed_holdout = int(rules["holdout_per_type"])
        needed_acquisition = int(rules["acquisition_per_type"])
        holdout = _take_independent(candidates[project_type], needed_holdout)
        blocked_owners = {row["owner"] for row in holdout}
        acquisition = _take_independent(
            [row for row in candidates[project_type] if row["owner"] not in blocked_owners],
            needed_acquisition,
        )
        splits.append({
            "project_type": project_type,
            "acquisition": acquisition,
            "holdout": holdout,
            "checks": _split_checks(acquisition, holdout),
        })
        shortages[project_type] = {
            "acquisition": max(0, needed_acquisition - len(acquisition)),
            "holdout": max(0, needed_holdout - len(holdout)),
        }
    local_shortage = any(any(value.values()) for value in shortages.values())
    external_used = _fill_external_shortage(
        root=base,
        splits=splits,
        shortages=shortages,
        external=list(rules.get("external_acquisition") or []),
        dynamically_exposed=dynamically_exposed,
    ) if local_shortage else []
    checks = {
        "source_index_is_local_and_sufficient": index.get("status") == "local_corpus_sufficient",
        "all_selected_untouched": True,
        "split_owner_independent": all(row["checks"]["owner_disjoint"] for row in splits),
        "split_content_independent": all(row["checks"]["content_disjoint"] for row in splits),
        "holdout_not_consumed": True,
        "external_only_after_local_shortage": not external_used or local_shortage,
        "external_revisions_bound": all(row.get("revision") for row in external_used),
        "no_source_apply": True,
        "no_promotion_applied": True,
    }
    remaining_shortage = any(any(value.values()) for value in shortages.values())
    body = {
        "artifact_type": "SelfDevelopmentChallengeManifest",
        "schema_version": "self_development_challenge_manifest.v1",
        "status": (
            "targeted_external_acquisition_ready" if external_used and not remaining_shortage and all(checks.values())
            else "local_corpus_sufficient" if not remaining_shortage and all(checks.values())
            else "local_corpus_shortage"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_index": str(rules["corpus_index"]),
        "dynamically_exposed_projects": len(dynamically_exposed),
        "scanned_projects": scanned,
        "candidate_counts": {key: len(candidates[key]) for key in rules["target_project_types"]},
        "splits": splits,
        "shortages": shortages,
        "network_fallback": {
            "allowed": local_shortage,
            "used": bool(external_used),
            "acquired_projects": external_used,
            "reason": "measured_local_shortage" if local_shortage else "local_corpus_sufficient",
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "safety": {"holdout_consumed": False, "source_apply": False, "promotion_applied": False},
    }
    return {**body, "manifest_digest": _digest(body)}


def run_challenge_campaign(
    *, root: Path, manifest: dict[str, Any], certification_receipt: str
) -> dict[str, Any]:
    base = root.resolve()
    if manifest.get("status") not in {"local_corpus_sufficient", "targeted_external_acquisition_ready"}:
        return _campaign_blocked(manifest, "manifest_not_ready")
    cases = []
    for split in manifest.get("splits") or []:
        for selected in split.get("acquisition") or []:
            project_dir = (base / str(selected["project_root"])).resolve()
            project_dir.relative_to(base)
            report = run_project_development(
                root=base,
                project_dir=project_dir,
                goal="Find a prospective systematic Cognitive OS error without changing source",
                prior_runs=[],
            )
            report_path = _write_project_report(base, report)
            collector = collect_project_development_report(root=base, report_path=report_path)
            actual = str(dict(dict(report.get("recognition") or {}).get("classification") or {}).get("project_stratum") or "")
            cases.append({
                "project": report.get("project"),
                "source": report_path.relative_to(base).as_posix(),
                "expected_project_type": selected.get("expected_project_type"),
                "actual_project_type": actual,
                "recognition_status": dict(report.get("recognition") or {}).get("status"),
                "issue_rules": sorted({
                    str(row.get("rule_id")) for row in dict(report.get("diagnosis") or {}).get("issues") or []
                    if isinstance(row, dict) and row.get("rule_id")
                }),
                "collector_status": collector.get("status"),
                "matched": actual == selected.get("expected_project_type"),
            })
    detection = run_prospective_detection(root=base, write=True)
    queue = build_self_development_experiment_queue(
        root=base, detection=detection, certification_receipt=certification_receipt
    )
    matched = sum(case["matched"] for case in cases)
    body = {
        "artifact_type": "SelfDevelopmentChallengeCampaignReport",
        "schema_version": "self_development_challenge_campaign_report.v1",
        "status": "completed" if matched == len(cases) else "completed_with_classification_mismatches",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_digest": manifest.get("manifest_digest"),
        "manifest_snapshot": {
            "source_index": manifest.get("source_index"),
            "scanned_projects": manifest.get("scanned_projects"),
            "candidate_counts": manifest.get("candidate_counts"),
            "splits": manifest.get("splits"),
            "checks": manifest.get("checks"),
            "safety": manifest.get("safety"),
        },
        "summary": {
            "executed": len(cases), "expected_type_matches": matched,
            "systematic_issue_cases": sum(bool(case["issue_rules"]) for case in cases),
            "detected_candidates": detection.get("candidate_count"),
            "experiment_ready_candidates": queue.get("ready_count"),
        },
        "coverage": _coverage(cases),
        "cases": cases,
        "detection": {"status": detection.get("status"), "report_path": detection.get("report_path")},
        "experiment_queue": queue,
        "safety": {"holdout_consumed": False, "source_apply": False, "promotion_applied": False},
    }
    return {**body, "campaign_digest": _digest(body)}


def _bounded_project_text(project: Path) -> str:
    names, chunks, total = [], [], 0
    skipped = {".git", ".hg", ".mypy_cache", ".pytest_cache", ".tox", ".venv", "venv", "node_modules", "__pycache__"}
    for current, dirs, files in os.walk(project):
        dirs[:] = sorted(name for name in dirs if name not in skipped and not name.startswith("."))
        for filename in sorted(files):
            path = Path(current) / filename
            relative = path.relative_to(project).as_posix().lower()
            if path.suffix.lower() == ".py" and len(names) < 64:
                names.append(relative)
            if filename.lower() not in {"pyproject.toml", "setup.cfg", "setup.py", "readme.md", "readme.rst"}:
                continue
            try:
                value = path.read_text(encoding="utf-8", errors="replace")[:8192].lower()
            except OSError:
                continue
            chunks.append(value)
            total += len(value)
            if total >= 32768:
                break
        if total >= 32768:
            break
    return "\n".join([project.name.lower(), *names[:64], *chunks])


def _signal_score(text: str, signals: list[str]) -> int:
    return sum(signal.lower() in text for signal in signals)


def _name_signal_matches(name: str, signal: str) -> bool:
    return re.search(
        rf"(?:^|[^a-z0-9]){re.escape(signal.lower())}(?:$|[^a-z0-9])",
        name.lower(),
    ) is not None


def _take_independent(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    result, owners, digests = [], set(), set()
    for row in rows:
        if row["owner"] in owners or row["content_digest"] in digests:
            continue
        result.append(row)
        owners.add(row["owner"])
        digests.add(row["content_digest"])
        if len(result) == count:
            break
    return result


def _fill_external_shortage(
    *, root: Path, splits: list[dict[str, Any]], shortages: dict[str, dict[str, int]],
    external: list[dict[str, Any]], dynamically_exposed: set[str],
) -> list[dict[str, Any]]:
    used = []
    for split in splits:
        project_type = str(split["project_type"])
        needed = int(shortages[project_type]["acquisition"])
        if needed <= 0:
            continue
        existing_owners = {row["owner"] for row in [*split["holdout"], *split["acquisition"]]}
        existing_digests = {row["content_digest"] for row in [*split["holdout"], *split["acquisition"]]}
        for raw in external:
            if raw.get("expected_project_type") != project_type or str(raw.get("project")).lower() in dynamically_exposed:
                continue
            project_root = (root / str(raw.get("project_root") or "")).resolve()
            project_root.relative_to(root)
            if not project_root.is_dir() or not raw.get("revision") or not raw.get("source_url"):
                continue
            digest = "sha256:" + hashlib.sha256(_bounded_project_text(project_root).encode()).hexdigest()
            owner = str(raw.get("owner") or "")
            if not owner or owner in existing_owners or digest in existing_digests:
                continue
            row = {
                **dict(raw), "canonical_project": str(raw["project"]).lower(),
                "content_digest": digest, "source_kind": "targeted_external_acquisition",
                "acquisition_reason": "measured_local_cli_shortage",
            }
            split["acquisition"].append(row)
            used.append(row)
            existing_owners.add(owner)
            existing_digests.add(digest)
            needed -= 1
            if needed == 0:
                break
        shortages[project_type]["acquisition"] = needed
        split["checks"] = _split_checks(split["acquisition"], split["holdout"])
    return used


def _split_checks(acquisition: list[dict[str, Any]], holdout: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "owner_disjoint": {row["owner"] for row in acquisition}.isdisjoint(row["owner"] for row in holdout),
        "content_disjoint": {row["content_digest"] for row in acquisition}.isdisjoint(row["content_digest"] for row in holdout),
    }


def _coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for expected in sorted({str(case["expected_project_type"]) for case in cases}):
        rows = [case for case in cases if case["expected_project_type"] == expected]
        result[expected] = {
            "executed": len(rows), "recognized_as_expected": sum(row["matched"] for row in rows),
            "recognition_failures": sum(row["recognition_status"] != "recognized" for row in rows),
            "systematic_issue_cases": sum(bool(row["issue_rules"]) for row in rows),
        }
    return result


def _write_project_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "project_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"project_development_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_inside(root: Path, value: str) -> dict[str, Any]:
    path = (root / value).resolve()
    path.relative_to(root)
    return json.loads(path.read_text(encoding="utf-8"))


def _exposed_projects(root: Path, pattern: str) -> set[str]:
    projects = set()
    for path in root.glob(pattern):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        project = str(payload.get("project") or "").lower()
        if project:
            projects.add(project)
    return projects


def _split_key(row: dict[str, Any], seed: str) -> str:
    return hashlib.sha256(f"{seed}:{row.get('canonical_project')}:{row.get('content_fingerprint')}".encode()).hexdigest()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _campaign_blocked(manifest: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "artifact_type": "SelfDevelopmentChallengeCampaignReport",
        "schema_version": "self_development_challenge_campaign_report.v1",
        "status": "blocked", "reason": reason, "manifest_digest": manifest.get("manifest_digest"),
        "summary": {"executed": 0}, "coverage": {}, "cases": [],
        "safety": {"holdout_consumed": False, "source_apply": False, "promotion_applied": False},
    }

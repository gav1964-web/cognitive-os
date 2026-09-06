"""Select untouched framework/plugin projects using owned structural contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from runtime.framework_plugin_contracts import git_head, owned_contracts, source_fingerprint


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "framework_plugin_holdout_selection.json"


class FrameworkPluginSelectionError(ValueError):
    """Raised when framework selection inputs violate their boundary."""


@lru_cache(maxsize=1)
def load_framework_selection_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "framework_plugin_holdout_selection.v1":
        raise FrameworkPluginSelectionError("framework selection schema mismatch")
    if payload.get("status") != "active":
        raise FrameworkPluginSelectionError("framework selection policy must be active")
    required = (
        "untouched_only",
        "root_manifest_authority",
        "project_owned_source_required",
        "owner_independence",
        "content_independence",
        "network_fallback_only_on_shortage",
    )
    invariants = dict(payload.get("invariants") or {})
    if not all(invariants.get(name) is True for name in required):
        raise FrameworkPluginSelectionError("framework selection invariants are incomplete")
    if invariants.get("source_apply") is not False:
        raise FrameworkPluginSelectionError("framework selection cannot apply source changes")
    if min(
        int(payload.get("minimum_acquisition_projects") or 0),
        int(payload.get("minimum_holdout_projects") or 0),
    ) < 1:
        raise FrameworkPluginSelectionError("framework split minima must be positive")
    return payload


def build_framework_plugin_holdout_selection(
    *,
    root: Path,
    eligibility: dict[str, Any],
    external_candidates: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_framework_selection_policy(
        str(base / "config" / "framework_plugin_holdout_selection.json")
    )
    projects = [
        dict(row)
        for row in eligibility.get("projects") or []
        if row.get("exposure") == "untouched"
    ]
    qualified = []
    for row in projects:
        project_root = _resolve(base, str(row.get("project_root") or ""))
        contracts = owned_contracts(project_root, rules)
        if contracts:
            qualified.append({
                "project": row.get("project"),
                "canonical_project": row.get("canonical_project"),
                "owner": row.get("owner"),
                "project_root": row.get("project_root"),
                "content_fingerprint": row.get("content_fingerprint"),
                "owned_contracts": contracts,
            })
    local_shortage = len(qualified) < (
        int(rules["minimum_holdout_projects"])
        + int(rules["minimum_acquisition_projects"])
    )
    external = _qualify_external_candidates(
        base, external_candidates or [], rules, allowed=local_shortage
    )
    ordered = sorted(
        [*qualified, *external],
        key=lambda row: _digest(
            f"{rules['split_seed']}:{row['canonical_project']}:{row['content_fingerprint']}"
        ),
    )
    holdout = _select_independent(ordered, int(rules["minimum_holdout_projects"]))
    holdout_ids = {row["canonical_project"] for row in holdout}
    acquisition = _select_independent(
        [row for row in ordered if row["canonical_project"] not in holdout_ids],
        int(rules["minimum_acquisition_projects"]),
    )
    shortage = {
        "acquisition": max(0, int(rules["minimum_acquisition_projects"]) - len(acquisition)),
        "holdout": max(0, int(rules["minimum_holdout_projects"]) - len(holdout)),
    }
    checks = {
        "eligibility_input_valid": eligibility.get("artifact_type")
        == "SelfDevelopmentCorpusEligibilityIndex"
        and not eligibility.get("failed_checks"),
        "all_selected_untouched": all(
            row.get("source") == "external_revision_bound"
            or row.get("canonical_project") in {
                item.get("canonical_project") for item in projects
            }
            for row in [*acquisition, *holdout]
        ),
        "all_selected_have_owned_contract": all(
            row.get("owned_contracts") for row in [*acquisition, *holdout]
        ),
        "owner_disjoint": _disjoint(acquisition, holdout, "owner"),
        "content_disjoint": _disjoint(acquisition, holdout, "content_fingerprint"),
        "external_only_after_local_shortage": not external or local_shortage,
        "external_revisions_verified": all(
            row.get("revision_verified") is True for row in external
        ),
        "no_source_apply": True,
        "no_promotion_applied": True,
    }
    network_required = any(shortage.values())
    body = {
        "artifact_type": "FrameworkPluginHoldoutSelection",
        "schema_version": "framework_plugin_holdout_selection_report.v1",
        "status": "local_corpus_sufficient" if not network_required else "local_corpus_shortage",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "eligibility_generated_at": eligibility.get("generated_at"),
        "scanned_untouched_projects": len(projects),
        "qualified_project_count": len(qualified) + len(external),
        "qualified_local_project_count": len(qualified),
        "qualified_external_project_count": len(external),
        "acquisition": acquisition,
        "holdout": holdout,
        "shortage": shortage,
        "network_fallback": {
            "required": local_shortage,
            "used": bool(external),
            "reason": "owned_contract_shortage" if local_shortage else "local_corpus_sufficient",
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "safety": {"source_apply": False, "promotion_applied": False},
    }
    report = {**body, "selection_digest": _digest(body)}
    if write:
        report["report_path"] = _write_report(base, report).as_posix()
    return report


def _qualify_external_candidates(
    root: Path,
    candidates: list[dict[str, Any]],
    policy: dict[str, Any],
    *,
    allowed: bool,
) -> list[dict[str, Any]]:
    if candidates and not allowed:
        raise FrameworkPluginSelectionError(
            "external candidates require a measured local owned-contract shortage"
        )
    qualified = []
    for candidate in candidates:
        project = _resolve(root, str(candidate.get("project_root") or ""))
        expected = str(candidate.get("revision") or "")
        actual = git_head(project)
        contracts = owned_contracts(project, policy)
        if not expected or actual != expected or not contracts:
            continue
        canonical = str(candidate.get("canonical_project") or "").lower()
        owner = str(candidate.get("owner") or "").lower()
        url = str(candidate.get("url") or "")
        if not canonical or not owner or not url.startswith("https://github.com/"):
            continue
        qualified.append({
            "project": canonical,
            "canonical_project": canonical,
            "owner": owner,
            "project_root": project.relative_to(root).as_posix(),
            "content_fingerprint": source_fingerprint(project, policy),
            "owned_contracts": contracts,
            "source": "external_revision_bound",
            "url": url,
            "revision": expected,
            "revision_verified": True,
            "acquisition_reason": "measured_owned_contract_shortage",
        })
    return qualified


def _select_independent(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected, owners, contents = [], set(), set()
    for row in rows:
        if row["owner"] in owners or row["content_fingerprint"] in contents:
            continue
        selected.append(row)
        owners.add(row["owner"])
        contents.add(row["content_fingerprint"])
        if len(selected) == count:
            break
    return selected


def _disjoint(left: list[dict[str, Any]], right: list[dict[str, Any]], key: str) -> bool:
    return not {row[key] for row in left}.intersection(row[key] for row in right)


def _resolve(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise FrameworkPluginSelectionError("framework project escapes workspace") from exc
    return path


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"framework_plugin_holdout_selection_{stamp}.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path

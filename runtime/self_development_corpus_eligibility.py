"""Index local corpora for contamination-aware self-development evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "self_development_corpus_eligibility.json"
SKIP_DIRS = {".git", ".hg", ".mypy_cache", ".pytest_cache", ".tox", ".venv", "node_modules", "probe_env", "venv"}
SOURCE_SAMPLE_LIMIT = 64
PROJECT_VALUE_PATTERN = re.compile(r'"(?:project|project_name)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')


class CorpusEligibilityError(ValueError):
    """Raised when the corpus eligibility boundary is invalid."""


@lru_cache(maxsize=1)
def load_corpus_eligibility_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "self_development_corpus_eligibility.v1":
        raise CorpusEligibilityError("corpus eligibility policy schema mismatch")
    if payload.get("status") != "active":
        raise CorpusEligibilityError("corpus eligibility policy must be active")
    required = (
        "corpus_root", "source_directory_name", "corpus_path_markers",
        "prospective_evidence_glob", "historical_evidence_glob", "target_markers",
        "identity_files", "split_seed",
    )
    if any(not payload.get(key) for key in required):
        raise CorpusEligibilityError("corpus eligibility scope is incomplete")
    if int(payload.get("minimum_python_files") or 0) < 1:
        raise CorpusEligibilityError("minimum Python file count must be positive")
    if min(int(payload.get("minimum_acquisition_projects") or 0), int(payload.get("minimum_holdout_projects") or 0)) < 1:
        raise CorpusEligibilityError("acquisition and holdout minima must be positive")
    invariants = dict(payload.get("invariants") or {})
    required_true = (
        "untouched_only", "owner_independence", "content_independence",
        "holdout_frozen_before_acquisition", "network_fallback_only_on_shortage",
    )
    if not all(invariants.get(key) is True for key in required_true):
        raise CorpusEligibilityError("corpus eligibility invariants are incomplete")
    if invariants.get("source_apply") is not False or invariants.get("promotion_applied") is not False:
        raise CorpusEligibilityError("corpus eligibility cannot mutate source or promote")
    return payload


def build_corpus_eligibility_index(
    *, root: Path, policy: dict[str, Any] | None = None, write: bool = False
) -> dict[str, Any]:
    base = root.resolve()
    rules = policy or load_corpus_eligibility_policy(
        str(base / "config" / "self_development_corpus_eligibility.json")
    )
    corpus_root = _resolve(base, str(rules["corpus_root"]))
    prospective = _collect_exposed_projects(base, str(rules["prospective_evidence_glob"]))
    historical = _collect_exposed_projects(base, str(rules["historical_evidence_glob"]))
    roots = _discover_project_roots(corpus_root, rules)
    records = [_project_record(base, path, rules, prospective, historical) for path in roots]
    canonical_groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        canonical_groups.setdefault(record["canonical_project"], []).append(record)
    unique = []
    for canonical, group in sorted(canonical_groups.items()):
        representative = sorted(group, key=lambda row: row["project_root"])[0]
        representative["copy_count"] = len(group)
        representative["alternate_roots"] = [row["project_root"] for row in sorted(group, key=lambda row: row["project_root"])[1:]]
        representative["content_variants"] = len({row["content_fingerprint"] for row in group})
        unique.append(representative)
    eligible = [row for row in unique if row["eligibility"] == "untouched_target_candidate"]
    ordered = sorted(eligible, key=lambda row: _split_key(row, str(rules["split_seed"])))
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
    network_required = any(shortage.values())
    summary = Counter(row["eligibility"] for row in unique)
    report = {
        "artifact_type": "SelfDevelopmentCorpusEligibilityIndex",
        "schema_version": "self_development_corpus_eligibility_index.v1",
        "status": "local_corpus_sufficient" if not network_required else "local_corpus_shortage",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "discovered_copies": len(records),
            "unique_projects": len(unique),
            "duplicate_copies": len(records) - len(unique),
            "eligibility": dict(sorted(summary.items())),
            "prospective_exposed_projects": len(prospective),
            "historically_exposed_projects": len(historical),
        },
        "target": "framework_plugin_build:packaging_build_backend",
        "acquisition": [_split_entry(row) for row in acquisition],
        "holdout": [_split_entry(row) for row in holdout],
        "shortage": shortage,
        "network_fallback": {"required": network_required, "reason": "local_split_shortage" if network_required else "local_corpus_sufficient"},
        "projects": unique,
        "checks": {
            "split_disjoint": not holdout_ids.intersection(row["canonical_project"] for row in acquisition),
            "acquisition_untouched": all(row["exposure"] == "untouched" for row in acquisition),
            "holdout_untouched": all(row["exposure"] == "untouched" for row in holdout),
            "owner_independent": _independent_owners(acquisition) and _independent_owners(holdout),
            "content_independent": _independent_content(acquisition) and _independent_content(holdout),
            "no_source_apply": True,
            "no_promotion_applied": True,
        },
        "safety": {"source_apply": False, "promotion_applied": False, "holdout_consumed": False},
    }
    report["failed_checks"] = [name for name, passed in report["checks"].items() if not passed]
    if write:
        report["report_path"] = _write_report(base, report).as_posix()
    return report


def _discover_project_roots(corpus_root: Path, policy: dict[str, Any]) -> list[Path]:
    source_name = str(policy["source_directory_name"])
    markers = tuple(str(item).lower() for item in policy["corpus_path_markers"])
    found: set[Path] = set()
    try:
        top_level = [path for path in corpus_root.iterdir() if path.is_dir()]
    except OSError as exc:
        raise CorpusEligibilityError("corpus root cannot be enumerated") from exc
    lineages = [path for path in top_level if any(marker in path.name.lower() for marker in markers)]
    for lineage_root in lineages:
        direct = lineage_root / source_name
        if direct.is_dir():
            source_dirs = [direct]
        else:
            source_dirs = []
            for current, dirs, _files in os.walk(lineage_root):
                dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
                path = Path(current)
                if path.name == source_name:
                    source_dirs.append(path)
                    dirs[:] = []
        for path in source_dirs:
            try:
                children = [child for child in path.iterdir() if child.is_dir() and child.name not in SKIP_DIRS]
            except OSError:
                continue
            for candidate in children:
                found.add(candidate.resolve())
    return sorted(found)


def _project_record(
    base: Path, project_root: Path, policy: dict[str, Any], prospective: set[str], historical: set[str]
) -> dict[str, Any]:
    canonical = _canonical(project_root.name)
    owner = canonical.split("__", 1)[0] if "__" in canonical else canonical
    identity_text = []
    digest = hashlib.sha256()
    python_files = 0
    manifest_files = 0
    identity_names = {str(item).lower() for item in policy["identity_files"]}
    try:
        root_files = [path for path in project_root.iterdir() if path.is_file()]
    except OSError:
        root_files = []
    for path in sorted(root_files):
        name = path.name
        if name.lower() not in identity_names:
            continue
        if name in {"pyproject.toml", "setup.cfg", "setup.py"}:
            manifest_files += 1
        try:
            data = path.read_bytes()[:131072]
        except OSError:
            continue
        digest.update(name.lower().encode("utf-8"))
        digest.update(data)
        identity_text.append(data.decode("utf-8", errors="ignore").lower())
    target_text = f"{project_root.name.lower()} {' '.join(identity_text)}"
    matched = sorted({marker for marker in policy["target_markers"] if str(marker).lower() in target_text})
    target_candidate = bool(matched) and manifest_files > 0
    source_limit = SOURCE_SAMPLE_LIMIT if target_candidate else int(policy["minimum_python_files"])
    for current, dirs, files in os.walk(project_root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = Path(current) / name
            relative = path.relative_to(project_root).as_posix()
            try:
                size = path.stat().st_size
            except OSError:
                continue
            digest.update(f"{relative}\0{size}\n".encode("utf-8"))
            python_files += 1
            try:
                digest.update(path.read_bytes()[:4096])
            except OSError:
                pass
            if python_files >= source_limit:
                break
        if python_files >= source_limit:
            break
    if canonical in prospective:
        exposure = "prospective_used"
    elif canonical in historical:
        exposure = "historically_exposed"
    else:
        exposure = "untouched"
    healthy = python_files >= int(policy["minimum_python_files"])
    if not healthy:
        eligibility = "insufficient_python_scope"
    elif exposure != "untouched":
        eligibility = exposure
    elif not target_candidate:
        eligibility = "untouched_non_target"
    else:
        eligibility = "untouched_target_candidate"
    return {
        "project": project_root.name,
        "canonical_project": canonical,
        "owner": owner,
        "project_root": project_root.relative_to(base).as_posix(),
        "content_fingerprint": digest.hexdigest(),
        "python_files_sampled": python_files,
        "python_file_count_capped": python_files >= source_limit,
        "manifest_files": manifest_files,
        "matched_target_markers": matched,
        "exposure": exposure,
        "eligibility": eligibility,
    }


def _collect_exposed_projects(root: Path, pattern: str) -> set[str]:
    exposed: set[str] = set()
    for path in sorted(root.glob(pattern)):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in PROJECT_VALUE_PATTERN.finditer(text):
            try:
                value = json.loads(f'"{match.group(1)}"')
            except json.JSONDecodeError:
                continue
            exposed.add(_canonical(value))
    return exposed


def _select_independent(rows: Iterable[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected, owners, fingerprints = [], set(), set()
    for row in rows:
        if row["owner"] in owners or row["content_fingerprint"] in fingerprints:
            continue
        selected.append(row)
        owners.add(row["owner"])
        fingerprints.add(row["content_fingerprint"])
        if len(selected) >= count:
            break
    return selected


def _split_key(row: dict[str, Any], seed: str) -> str:
    return hashlib.sha256(f"{seed}:{row['canonical_project']}:{row['content_fingerprint']}".encode()).hexdigest()


def _split_entry(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in (
        "project", "canonical_project", "owner", "project_root", "content_fingerprint", "matched_target_markers", "exposure"
    )}


def _independent_owners(rows: list[dict[str, Any]]) -> bool:
    return len(rows) == len({row["owner"] for row in rows})


def _independent_content(rows: list[dict[str, Any]]) -> bool:
    return len(rows) == len({row["content_fingerprint"] for row in rows})


def _canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "-", value.strip().lower()).strip("-")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CorpusEligibilityError("corpus path escapes workspace") from exc
    return resolved


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_development"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_development_corpus_eligibility_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

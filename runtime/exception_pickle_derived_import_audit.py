"""Read-only import-isolation audit for derived-message exception replay."""

from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_holdout_transaction import DEFAULT_AUDIT


DEFAULT_DERIVED_AUDIT = Path(
    "artifacts/project_development/exception_pickle_derived_message_audit_20260901T114434207089Z.json"
)


def run_exception_pickle_derived_import_audit(
    *,
    root: Path,
    derived_message_audit_path: Path = DEFAULT_DERIVED_AUDIT,
    candidate_audit_path: Path = DEFAULT_AUDIT,
) -> dict[str, Any]:
    root = root.resolve()
    derived = _read_json(root, derived_message_audit_path)
    candidate_audit = _read_json(root, candidate_audit_path)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in candidate_audit.get("candidates") or []
        if isinstance(row, dict)
    }
    cases: list[dict[str, Any]] = []
    lane_counter: Counter[str] = Counter()
    project_counter: Counter[str] = Counter()
    for case in derived.get("cases") or []:
        if not isinstance(case, dict):
            continue
        if case.get("derived_message_lane") != "derived_message_import_isolation_first":
            continue
        key = f"{case.get('project')}::{case.get('target')}"
        row = rows_by_key.get(key)
        profile = _import_profile(root, row)
        lane = _import_lane(profile)
        lane_counter[lane] += 1
        project_counter[str(case.get("project") or "")] += 1
        cases.append({
            "project": case.get("project"),
            "target": case.get("target"),
            "import_isolation_lane": lane,
            "required_input_signature": case.get("required_input_signature"),
            "replay_risk": case.get("replay_risk"),
            "import_profile": profile,
        })
    sequence = _recommended_sequence(lane_counter)
    return {
        "artifact_type": "ExceptionPickleDerivedImportAudit",
        "schema_version": "exception_pickle_derived_import_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "derived_message_audit": str(derived_message_audit_path),
        "candidate_audit": str(candidate_audit_path),
        "case_count": len(cases),
        "lane_summary": dict(sorted(lane_counter.items())),
        "top_projects": _top(project_counter, 8),
        "recommended_next_lane": sequence[0] if sequence else None,
        "recommended_sequence": sequence,
        "cases": cases,
        "source_apply": False,
        "kb_promotion": False,
        "llm_authority": "advisory_only",
    }


def write_exception_pickle_derived_import_audit(
    *,
    root: Path,
    derived_message_audit_path: Path = DEFAULT_DERIVED_AUDIT,
    candidate_audit_path: Path = DEFAULT_AUDIT,
) -> dict[str, Any]:
    report = run_exception_pickle_derived_import_audit(
        root=root,
        derived_message_audit_path=derived_message_audit_path,
        candidate_audit_path=candidate_audit_path,
    )
    output = root / "artifacts" / "project_development" / (
        "exception_pickle_derived_import_audit_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = output.as_posix()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _import_profile(root: Path, row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"available": False, "reason": "candidate_row_missing"}
    project = root / str(row.get("project_root") or "")
    target = Path(str(row.get("path") or ""))
    target_profile = _source_profile(project / target)
    init_profiles = [
        _source_profile(project / parent / "__init__.py")
        for parent in target.parents
        if str(parent) != "."
    ]
    package_init_risk = sum(int(profile.get("risk") or 0) for profile in init_profiles)
    target_risk = int(target_profile.get("risk") or 0)
    metadata_calls = int(target_profile.get("metadata_version_calls") or 0) + sum(
        int(profile.get("metadata_version_calls") or 0) for profile in init_profiles
    )
    return {
        "available": True,
        "target_file": target.as_posix(),
        "target_risk": target_risk,
        "package_init_risk": package_init_risk,
        "total_risk": target_risk + package_init_risk * 3,
        "target_import_count": target_profile.get("import_count", 0),
        "package_init_file_count": len([profile for profile in init_profiles if profile.get("exists")]),
        "package_init_import_count": sum(int(profile.get("import_count") or 0) for profile in init_profiles),
        "metadata_version_calls": metadata_calls,
        "target_parse_failed": target_profile.get("parse_failed") is True,
        "package_init_parse_failed": any(profile.get("parse_failed") is True for profile in init_profiles),
        "declared_target_stub_modules": target_profile.get("declared_stub_modules", []),
    }


def _source_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "risk": 0, "import_count": 0, "metadata_version_calls": 0}
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"exists": True, "parse_failed": True, "risk": 20, "import_count": 0, "metadata_version_calls": 0}
    import_count = 0
    raise_count = 0
    metadata_calls = 0
    stub_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_count += len(node.names)
            for alias in node.names:
                stub_modules.update(_module_prefixes(alias.name))
        elif isinstance(node, ast.ImportFrom):
            import_count += 1
            if node.level == 0 and node.module:
                stub_modules.update(_module_prefixes(node.module))
        elif isinstance(node, ast.Raise):
            raise_count += 1
        elif isinstance(node, ast.Call) and _is_metadata_version_call(node):
            metadata_calls += 1
    return {
        "exists": True,
        "parse_failed": False,
        "risk": import_count + raise_count * 5 + metadata_calls * 4,
        "import_count": import_count,
        "raise_count": raise_count,
        "metadata_version_calls": metadata_calls,
        "declared_stub_modules": sorted(stub_modules),
    }


def _import_lane(profile: dict[str, Any]) -> str:
    if profile.get("available") is not True:
        return "derived_import_source_missing"
    if profile.get("target_parse_failed") or profile.get("package_init_parse_failed"):
        return "derived_import_parse_first"
    if int(profile.get("metadata_version_calls") or 0) > 0:
        return "derived_import_metadata_side_effect"
    target_risk = int(profile.get("target_risk") or 0)
    package_risk = int(profile.get("package_init_risk") or 0)
    if package_risk > target_risk:
        return "derived_import_direct_file_fallback_candidate"
    if int(profile.get("target_import_count") or 0) > 0:
        return "derived_import_target_stub_candidate"
    return "derived_import_runtime_probe_needed"


def _recommended_sequence(counter: Counter[str]) -> list[dict[str, Any]]:
    priority = {
        "derived_import_direct_file_fallback_candidate": 100,
        "derived_import_target_stub_candidate": 90,
        "derived_import_metadata_side_effect": 70,
        "derived_import_parse_first": 50,
        "derived_import_runtime_probe_needed": 40,
        "derived_import_source_missing": 10,
    }
    return [
        {
            "lane": lane,
            "case_count": count,
            "priority": priority.get(lane, 0),
            "next_action": _next_action(lane),
        }
        for lane, count in sorted(counter.items(), key=lambda item: (-priority.get(item[0], 0), -item[1], item[0]))
    ]


def _next_action(lane: str) -> str:
    actions = {
        "derived_import_direct_file_fallback_candidate": "prefer direct-file replay for package-init-heavy cases",
        "derived_import_target_stub_candidate": "expand target-declared import stubs only with source evidence",
        "derived_import_metadata_side_effect": "isolate metadata.version and package discovery side effects",
        "derived_import_parse_first": "repair source parsing or mark corpus hygiene",
        "derived_import_runtime_probe_needed": "collect runtime import failure evidence",
    }
    return actions.get(lane, "collect evidence")


def _candidate_key(row: dict[str, Any]) -> str:
    project = str(row.get("canonical_project") or row.get("project") or "")
    target = f"{row.get('path')}:{row.get('class_name')}.__init__"
    return f"{project}::{target}"


def _module_prefixes(name: str) -> set[str]:
    parts = [part for part in name.split(".") if part.isidentifier()]
    return {".".join(parts[:index]) for index in range(1, len(parts) + 1)}


def _is_metadata_version_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "version":
        try:
            return "metadata" in ast.unparse(func.value)
        except Exception:
            return False
    return False


def _top(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload

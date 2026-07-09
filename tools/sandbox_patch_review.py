"""Review and explicitly apply sandbox patch packages."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-dir", required=True)
    parser.add_argument("--expected-source-project")
    parser.add_argument("--write-review", action="store_true")
    parser.add_argument("--apply-approved", action="store_true")
    args = parser.parse_args()

    report = review_patch_package(
        patch_dir=Path(args.patch_dir).resolve(),
        expected_source_project=Path(args.expected_source_project).resolve() if args.expected_source_project else None,
        write_review=args.write_review,
        apply_approved=args.apply_approved,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"review_ready", "applied"} else 1


def review_patch_package(
    *,
    patch_dir: Path,
    expected_source_project: Path | None = None,
    write_review: bool = False,
    apply_approved: bool = False,
) -> dict[str, Any]:
    package_report = _load_package_report(patch_dir)
    source_project = Path(str(package_report["source_project"])).resolve()
    package_root = patch_dir / "package"
    target_files = _target_files(package_root, source_project)
    validation = _validate_package(package_report, source_project, expected_source_project, target_files)
    diffs = [_diff_file(source, patched) for source, patched in target_files]
    review = {
        "artifact_type": "SandboxPatchReview",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "patch_dir": patch_dir.as_posix(),
        "source_project": source_project.as_posix(),
        "package_status": package_report.get("status"),
        "package_verification": package_report.get("verification", {}).get("status"),
        "target_files": [
            {
                "source": source.as_posix(),
                "patched": patched.as_posix(),
                "exists": source.exists(),
                "diff_lines": len(diff["diff"]),
            }
            for (source, patched), diff in zip(target_files, diffs)
        ],
        "risk_summary": _risk_summary(package_report, diffs),
        "validation": validation,
        "diffs": diffs,
        "apply": {
            "requested": apply_approved,
            "requires_flag": "--apply-approved",
            "status": "not_requested",
        },
        "status": "review_ready" if validation["status"] == "ok" else "blocked",
    }
    if write_review:
        (patch_dir / "patch_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (patch_dir / "patch_review.md").write_text(_review_markdown(review), encoding="utf-8")
        review["review_json"] = (patch_dir / "patch_review.json").as_posix()
        review["review_markdown"] = (patch_dir / "patch_review.md").as_posix()
    if apply_approved:
        review["apply"] = _apply_patch_package(target_files, validation)
        review["status"] = "applied" if review["apply"]["status"] == "applied" else "blocked"
    return review


def _load_package_report(patch_dir: Path) -> dict[str, Any]:
    report_path = patch_dir / "patch_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    return json.loads(report_path.read_text(encoding="utf-8"))


def _target_files(package_root: Path, source_project: Path) -> list[tuple[Path, Path]]:
    if not package_root.is_dir():
        raise FileNotFoundError(package_root)
    targets: list[tuple[Path, Path]] = []
    for patched in sorted(path for path in package_root.rglob("*") if path.is_file()):
        if any(part in {".pytest_cache", "__pycache__"} for part in patched.parts) or patched.name.endswith((".pyc", ".pyo")):
            continue
        rel = patched.relative_to(package_root)
        if rel.parts and rel.parts[0] == "tests":
            continue
        targets.append((source_project / rel, patched))
    return targets


def _validate_package(
    package_report: dict[str, Any],
    source_project: Path,
    expected_source_project: Path | None,
    target_files: list[tuple[Path, Path]],
) -> dict[str, Any]:
    blockers: list[str] = []
    if package_report.get("artifact_type") != "SandboxPatchPackage":
        blockers.append("not_a_sandbox_patch_package")
    if package_report.get("status") != "ok":
        blockers.append("package_status_not_ok")
    if package_report.get("verification", {}).get("status") != "passed":
        blockers.append("verification_not_passed")
    if package_report.get("source_code_changes") is not False:
        blockers.append("package_must_start_as_no_source_change")
    if package_report.get("registry_changes") is not False:
        blockers.append("registry_changes_not_allowed")
    if expected_source_project and not _same_path(source_project, expected_source_project):
        blockers.append("source_project_mismatch")
    if not target_files:
        blockers.append("no_target_files")
    if any(not source.exists() for source, _ in target_files):
        blockers.append("target_source_file_missing")
    if not source_project.is_dir():
        blockers.append("source_project_missing")
    return {"status": "blocked" if blockers else "ok", "blockers": blockers}


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _diff_file(source: Path, patched: Path) -> dict[str, Any]:
    source_text = source.read_text(encoding="utf-8").splitlines(keepends=True) if source.exists() else []
    patched_text = patched.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            source_text,
            patched_text,
            fromfile=source.as_posix(),
            tofile=patched.as_posix(),
            lineterm="",
        )
    )
    return {
        "source": source.as_posix(),
        "patched": patched.as_posix(),
        "diff": diff,
        "added_lines": sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")),
        "removed_lines": sum(1 for line in diff if line.startswith("-") and not line.startswith("---")),
    }


def _risk_summary(package_report: dict[str, Any], diffs: list[dict[str, Any]]) -> list[str]:
    risks: list[str] = []
    if package_report.get("target_model"):
        risks.append(f"provider migration target: {package_report['target_model']}")
    if any("GIGACHAT_AUTH_KEY" in "\n".join(diff["diff"]) for diff in diffs):
        risks.append("requires runtime secret via environment")
    if any("requests.post" in "\n".join(diff["diff"]) for diff in diffs):
        risks.append("changes external network boundary")
    if any(diff["removed_lines"] or diff["added_lines"] for diff in diffs):
        risks.append("source behavior changes require project-level regression tests")
    return risks or ["no textual source diff detected"]


def _apply_patch_package(target_files: list[tuple[Path, Path]], validation: dict[str, Any]) -> dict[str, Any]:
    if validation["status"] != "ok":
        return {"status": "blocked", "reason": "validation_failed", "blockers": validation["blockers"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    applied: list[dict[str, str]] = []
    for source, patched in target_files:
        backup = source.with_name(f"{source.name}.bak.{stamp}")
        shutil.copy2(source, backup)
        shutil.copy2(patched, source)
        applied.append({"source": source.as_posix(), "backup": backup.as_posix(), "patched_from": patched.as_posix()})
    return {"status": "applied", "applied_files": applied}


def _review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Sandbox Patch Review",
        "",
        f"Status: `{review['status']}`",
        f"Source project: `{review['source_project']}`",
        f"Package verification: `{review['package_verification']}`",
        "",
        "## Risks",
        "",
    ]
    lines.extend(f"- {risk}" for risk in review["risk_summary"])
    lines.extend(["", "## Target Files", ""])
    lines.extend(f"- `{item['source']}` from `{item['patched']}` ({item['diff_lines']} diff lines)" for item in review["target_files"])
    lines.extend(["", "## Validation", "", f"`{review['validation']['status']}`"])
    for blocker in review["validation"]["blockers"]:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Diff", ""])
    for diff in review["diffs"]:
        lines.extend(["```diff", *diff["diff"][:400], "```", ""])
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

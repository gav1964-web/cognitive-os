"""Run a teacher-corrected LLM migration trial for the map project."""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from gigachat_sandbox_patch import build_patch
    from llm_migration_analysis import analyze_llm_migration
    from sandbox_patch_review import review_patch_package
except ModuleNotFoundError:
    from tools.gigachat_sandbox_patch import build_patch
    from tools.llm_migration_analysis import analyze_llm_migration
    from tools.sandbox_patch_review import review_patch_package


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--source-project", required=True)
    parser.add_argument("--target-model", default="GigaChat-2-Pro")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = run_trial(
        root=Path(args.root).resolve(),
        source_project=Path(args.source_project).resolve(),
        target_model=args.target_model,
        write=args.write,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_trial(*, root: Path, source_project: Path, target_model: str, write: bool = False) -> dict[str, Any]:
    out_dir = _trial_dir(root)
    fixture = out_dir / "map_baseline_fixture"
    teacher_file = source_project / "import_indoc.py"
    baseline_file = _latest_backup(source_project)
    if not teacher_file.is_file():
        raise FileNotFoundError(teacher_file)
    if baseline_file is None:
        raise FileNotFoundError("import_indoc.py.bak.* baseline not found")

    fixture.mkdir(parents=True)
    shutil.copy2(baseline_file, fixture / "import_indoc.py")
    if (source_project / "requirements.txt").is_file():
        shutil.copy2(source_project / "requirements.txt", fixture / "requirements.txt")

    analysis = analyze_llm_migration(project_dir=fixture, target_model=target_model)
    package = build_patch(root=root, project_dir=fixture, target_model=target_model)
    review = review_patch_package(
        patch_dir=Path(str(package["sandbox_dir"])),
        expected_source_project=fixture,
        write_review=write,
        apply_approved=True,
    )

    compile_result = _compile_file(fixture / "import_indoc.py")
    teacher_text = teacher_file.read_text(encoding="utf-8")
    result_text = (fixture / "import_indoc.py").read_text(encoding="utf-8")
    comparison = _compare_result(_normalize(teacher_text), _normalize(result_text), target_model)

    status = "ok" if _is_ok(analysis, package, review, compile_result, comparison) else "failed"
    report = {
        "artifact_type": "MapLlmMigrationTrial",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project": source_project.as_posix(),
        "baseline_source": baseline_file.as_posix(),
        "teacher_reference": {
            "kind": "external_teacher_corrector_patch",
            "quality": "teacher_reference_not_ground_truth",
            "file": teacher_file.as_posix(),
        },
        "trial_fixture": fixture.as_posix(),
        "analysis": {
            "status": analysis.get("status"),
            "llm_files": analysis.get("llm_files", []),
            "recommendations": analysis.get("recommendations", []),
        },
        "patch_package": {
            "status": package.get("status"),
            "sandbox_dir": package.get("sandbox_dir"),
            "verification": dict(package.get("verification", {})).get("status"),
        },
        "review_apply": {
            "status": review.get("status"),
            "apply_status": dict(review.get("apply", {})).get("status"),
            "validation": review.get("validation"),
            "risk_summary": review.get("risk_summary"),
        },
        "verification": compile_result,
        "comparison": comparison,
        "invariants": {
            "source_project_modified": False,
            "fixture_only_apply": True,
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
        },
    }
    if write:
        report_path = out_dir / "map_llm_migration_trial.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = report_path.as_posix()
    return report


def _latest_backup(source_project: Path) -> Path | None:
    backups = sorted(source_project.glob("import_indoc.py.bak.*"), key=lambda path: path.name)
    return backups[-1] if backups else None


def _compile_file(path: Path) -> dict[str, Any]:
    result = subprocess.run([sys.executable, "-m", "py_compile", str(path)], capture_output=True, text=True, timeout=60)
    return {
        "command": f"{sys.executable} -m py_compile {path.as_posix()}",
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-1200:],
    }


def _compare_result(teacher: str, result: str, target_model: str) -> dict[str, Any]:
    features = {
        "target_model": target_model in result,
        "local_proxy_removed": "http://127.0.0.1:8000/v1/chat/completions" not in result,
        "client_secret_alias": "GIGACHAT_CLIENT_SECRET" in result,
        "auth_key_alias": "GIGACHAT_AUTH_KEY" in result,
        "verify_ssl_env": "GIGACHAT_VERIFY_SSL" in result,
        "bearer_header": "Bearer" in result and "Authorization" in result,
        "oauth_rquid": "RqUID" in result,
        "provider_cache_key": '"provider": "gigachat"' in result,
        "fallback_error_message": "GIGACHAT_AUTH_KEY or GIGACHAT_ACCESS_TOKEN" in result,
        "schema_detail_preserved": "населенный пункт без префикса" in result,
        "qwen_help_removed": "Qwen" not in result,
    }
    diff = list(difflib.unified_diff(teacher.splitlines(), result.splitlines(), fromfile="teacher", tofile="trial", lineterm=""))
    return {
        "exact_match": teacher == result,
        "feature_score": sum(1 for ok in features.values() if ok),
        "feature_total": len(features),
        "features": features,
        "diff_lines": len(diff),
        "diff_head": diff[:80],
    }


def _is_ok(
    analysis: dict[str, Any],
    package: dict[str, Any],
    review: dict[str, Any],
    compile_result: dict[str, Any],
    comparison: dict[str, Any],
) -> bool:
    return (
        analysis.get("status") in {"needs_migration", "partial"}
        and package.get("status") == "ok"
        and dict(package.get("verification", {})).get("status") == "passed"
        and review.get("status") == "applied"
        and dict(review.get("apply", {})).get("status") == "applied"
        and compile_result.get("status") == "passed"
        and comparison.get("feature_score") == comparison.get("feature_total")
    )


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def _trial_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / "artifacts" / "map_llm_migration_trials" / f"trial_{stamp}"


if __name__ == "__main__":
    raise SystemExit(main())

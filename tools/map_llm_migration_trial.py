"""Run a teacher-corrected LLM migration trial for the map project."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_change_trial import (
    FeatureNeedle,
    TrialFile,
    build_trial_report,
    compare_text_files,
    copy_optional_files,
    create_fixture,
    create_trial_dir,
    write_report,
)

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
    out_dir = create_trial_dir(root, "map_llm_migration_trials", "trial")
    teacher_file = source_project / "import_indoc.py"
    baseline_file = _latest_backup(source_project)
    if not teacher_file.is_file():
        raise FileNotFoundError(teacher_file)
    if baseline_file is None:
        raise FileNotFoundError("import_indoc.py.bak.* baseline not found")

    fixture = create_fixture(out_dir, "map_baseline_fixture", [TrialFile("import_indoc.py", baseline_file)])
    copied_optional = copy_optional_files(source_project, fixture, ["requirements.txt"])

    analysis = analyze_llm_migration(project_dir=fixture, target_model=target_model)
    package = build_patch(root=root, project_dir=fixture, target_model=target_model)
    review = review_patch_package(
        patch_dir=Path(str(package["sandbox_dir"])),
        expected_source_project=fixture,
        write_review=write,
        apply_approved=True,
    )

    compile_result = _compile_file(fixture / "import_indoc.py")
    comparison = compare_text_files(
        teacher_path=teacher_file,
        result_path=fixture / "import_indoc.py",
        feature_needles=_feature_needles(target_model),
    )

    status = "ok" if _is_ok(analysis, package, review, compile_result, comparison) else "failed"
    report = build_trial_report(
        artifact_type="MapLlmMigrationTrial",
        status=status,
        source_project=source_project,
        trial_fixture=fixture,
        teacher_file=teacher_file,
        baseline_sources=[baseline_file],
        sections={
            "baseline_source": baseline_file.as_posix(),
            "optional_files_copied": copied_optional,
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
        },
    )
    if write:
        report_path = write_report(report, out_dir, "map_llm_migration_trial.json")
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


def _feature_needles(target_model: str) -> list[FeatureNeedle]:
    return [
        FeatureNeedle("target_model", present=(target_model,)),
        FeatureNeedle("local_proxy_removed", absent=("http://127.0.0.1:8000/v1/chat/completions",)),
        FeatureNeedle("client_secret_alias", present=("GIGACHAT_CLIENT_SECRET",)),
        FeatureNeedle("auth_key_alias", present=("GIGACHAT_AUTH_KEY",)),
        FeatureNeedle("verify_ssl_env", present=("GIGACHAT_VERIFY_SSL",)),
        FeatureNeedle("bearer_header", present=("Bearer", "Authorization")),
        FeatureNeedle("oauth_rquid", present=("RqUID",)),
        FeatureNeedle("provider_cache_key", present=('"provider": "gigachat"',)),
        FeatureNeedle("fallback_error_message", present=("GIGACHAT_AUTH_KEY or GIGACHAT_ACCESS_TOKEN",)),
        FeatureNeedle("schema_detail_preserved", present=("населенный пункт без префикса",)),
        FeatureNeedle("qwen_help_removed", absent=("Qwen",)),
    ]



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


if __name__ == "__main__":
    raise SystemExit(main())

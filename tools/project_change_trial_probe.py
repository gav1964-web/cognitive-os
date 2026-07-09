"""Portable acceptance probe for the project-change teacher/corrector contour."""

from __future__ import annotations

import argparse
import json
import shutil
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


BASELINE = '''PROVIDER = "local-proxy"
MODEL = "qwen"


def call_provider(payload):
    return {"provider": PROVIDER, "model": MODEL, "payload": payload}
'''


TEACHER = '''PROVIDER = "direct-provider"
MODEL = "GigaChat-2-Pro"
TOKEN_ENV = "GIGACHAT_CLIENT_SECRET"


def call_provider(payload):
    return {"provider": PROVIDER, "model": MODEL, "payload": payload}
'''


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = run_probe(root=Path(args.root).resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(*, root: Path, write: bool = False) -> dict[str, Any]:
    source_project = root / "artifacts" / "project_change_trial_probe" / "source_project"
    if source_project.parent.exists():
        shutil.rmtree(source_project.parent)
    source_project.mkdir(parents=True)
    baseline = source_project / "client.py.bak.0"
    teacher = source_project / "client.py"
    baseline.write_text(BASELINE, encoding="utf-8")
    teacher.write_text(TEACHER, encoding="utf-8")
    (source_project / "requirements.txt").write_text("requests\n", encoding="utf-8")

    source_before = teacher.read_text(encoding="utf-8")
    out_dir = create_trial_dir(root, "project_change_trials", "probe")
    fixture = create_fixture(out_dir, "fixture", [TrialFile("client.py", baseline)])
    copied_optional = copy_optional_files(source_project, fixture, ["requirements.txt"])

    # Simulates an already reviewed sandbox apply into the fixture only.
    (fixture / "client.py").write_text(teacher.read_text(encoding="utf-8"), encoding="utf-8")
    comparison = compare_text_files(
        teacher_path=teacher,
        result_path=fixture / "client.py",
        feature_needles=[
            FeatureNeedle("target_model", present=("GigaChat-2-Pro",)),
            FeatureNeedle("secret_env", present=("GIGACHAT_CLIENT_SECRET",)),
            FeatureNeedle("local_proxy_removed", absent=("local-proxy", "qwen")),
        ],
    )
    source_after = teacher.read_text(encoding="utf-8")
    status = "ok" if _is_ok(comparison, copied_optional, source_before == source_after) else "failed"
    report = build_trial_report(
        artifact_type="ProjectChangeTrialProbe",
        status=status,
        source_project=source_project,
        trial_fixture=fixture,
        teacher_file=teacher,
        baseline_sources=[baseline],
        sections={
            "optional_files_copied": copied_optional,
            "comparison": comparison,
            "simulated_apply": {
                "target": "fixture",
                "status": "applied",
                "source_project_unchanged": source_before == source_after,
            },
        },
    )
    if write:
        report_path = write_report(report, out_dir, "project_change_trial_probe.json")
        report["report_path"] = report_path.as_posix()
    return report


def _is_ok(comparison: dict[str, Any], copied_optional: list[str], source_unchanged: bool) -> bool:
    return (
        comparison.get("exact_match") is True
        and comparison.get("feature_score") == comparison.get("feature_total")
        and copied_optional == ["requirements.txt"]
        and source_unchanged
    )


if __name__ == "__main__":
    raise SystemExit(main())

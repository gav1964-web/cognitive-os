"""Declarative project-change trial scenarios."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

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


def run_project_change_scenario(*, root: Path, scenario_path: Path, write: bool = False) -> dict[str, Any]:
    scenario_path = scenario_path.resolve()
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    base_dir = scenario_path.parent
    source_project = _resolve(base_dir, scenario["source_project"])
    teacher_file = _resolve(base_dir, scenario["teacher_reference"]["file"])
    files = [
        TrialFile(
            target_relative=str(item["target_relative"]),
            baseline_path=_resolve(base_dir, item["baseline"]),
        )
        for item in scenario.get("files", [])
    ]
    if not files:
        raise ValueError("scenario.files must contain at least one baseline file")

    out_dir = create_trial_dir(
        root,
        str(scenario.get("artifact_group", "project_change_trials")),
        str(scenario.get("label", scenario.get("id", "scenario"))),
    )
    fixture = create_fixture(out_dir, str(scenario.get("fixture_name", "fixture")), files)
    copied_optional = copy_optional_files(source_project, fixture, [str(path) for path in scenario.get("optional_files", [])])
    _apply_scenario(base_dir=base_dir, fixture=fixture, scenario=scenario)

    comparisons = [
        compare_text_files(
            teacher_path=_resolve(base_dir, item.get("teacher", scenario["teacher_reference"]["file"])),
            result_path=fixture / str(item["target_relative"]),
            feature_needles=_feature_needles(item.get("features", [])),
        )
        for item in scenario.get("comparisons", [])
    ]
    if not comparisons:
        comparisons = [
            compare_text_files(
                teacher_path=teacher_file,
                result_path=fixture / files[0].target_relative,
                feature_needles=_feature_needles(scenario.get("feature_needles", [])),
            )
        ]

    status = "ok" if _scenario_ok(comparisons) else "failed"
    report = build_trial_report(
        artifact_type=str(scenario.get("artifact_type", "ProjectChangeScenarioTrial")),
        status=status,
        source_project=source_project,
        trial_fixture=fixture,
        teacher_file=teacher_file,
        baseline_sources=[item.baseline_path for item in files],
        sections={
            "scenario": {
                "id": scenario.get("id"),
                "path": scenario_path.as_posix(),
                "apply_type": dict(scenario.get("apply", {})).get("type"),
            },
            "optional_files_copied": copied_optional,
            "comparisons": comparisons,
            "comparison": comparisons[0],
            "simulated_apply": {
                "target": "fixture",
                "status": "applied",
                "source_project_unchanged": True,
            },
        },
    )
    if write:
        report_path = write_report(report, out_dir, "project_change_scenario_trial.json")
        report["report_path"] = report_path.as_posix()
    return report


def _apply_scenario(*, base_dir: Path, fixture: Path, scenario: dict[str, Any]) -> None:
    apply_spec = dict(scenario.get("apply", {}))
    apply_type = apply_spec.get("type", "copy_teacher_to_fixture")
    if apply_type != "copy_teacher_to_fixture":
        raise ValueError(f"unsupported scenario apply type: {apply_type}")
    for item in scenario.get("files", []):
        teacher = _resolve(base_dir, item.get("teacher", scenario["teacher_reference"]["file"]))
        target = fixture / str(item["target_relative"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(teacher, target)


def _feature_needles(items: list[dict[str, Any]]) -> list[FeatureNeedle]:
    return [
        FeatureNeedle(
            name=str(item["name"]),
            present=tuple(str(value) for value in item.get("present", [])),
            absent=tuple(str(value) for value in item.get("absent", [])),
        )
        for item in items
    ]


def _scenario_ok(comparisons: list[dict[str, Any]]) -> bool:
    return all(
        item.get("exact_match") is True and item.get("feature_score") == item.get("feature_total")
        for item in comparisons
    )


def _resolve(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path

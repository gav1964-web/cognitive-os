"""Declarative project-change trial scenarios."""

from __future__ import annotations

import json
import shutil
import hashlib
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
    validation = validate_project_change_scenario(scenario=scenario, base_dir=base_dir)
    if validation["status"] != "ok":
        raise ValueError("; ".join(validation["errors"]))
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
    source_before = _snapshot_project(source_project)
    apply_result = _apply_scenario(base_dir=base_dir, fixture=fixture, scenario=scenario, root=root, write=write)
    source_after = _snapshot_project(source_project)
    apply_result["source_project_unchanged"] = source_before == source_after

    comparisons = [
        _comparison_with_policy(
            teacher_path=_resolve(base_dir, item.get("teacher", scenario["teacher_reference"]["file"])),
            result_path=fixture / str(item["target_relative"]),
            feature_needles=_feature_needles(item.get("features", [])),
            exact_match_required=bool(item.get("exact_match_required", True)),
        )
        for item in scenario.get("comparisons", [])
    ]
    if not comparisons:
        comparisons = [
            _comparison_with_policy(
                teacher_path=teacher_file,
                result_path=fixture / files[0].target_relative,
                feature_needles=_feature_needles(scenario.get("feature_needles", [])),
                exact_match_required=True,
            )
        ]

    status = (
        "ok"
        if apply_result.get("status") == "applied" and apply_result.get("source_project_unchanged") is True and _scenario_ok(comparisons)
        else "failed"
    )
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
            "apply_result": apply_result,
            "simulated_apply": apply_result,
        },
    )
    if write:
        report_path = write_report(report, out_dir, "project_change_scenario_trial.json")
        report["report_path"] = report_path.as_posix()
    return report


def validate_project_change_scenario(*, scenario: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(scenario, dict):
        return {"status": "failed", "errors": ["scenario must be an object"]}
    _require_string(scenario, "id", errors)
    _require_string(scenario, "source_project", errors)
    teacher_reference = scenario.get("teacher_reference")
    if not isinstance(teacher_reference, dict):
        errors.append("teacher_reference must be an object")
    else:
        _require_string(teacher_reference, "file", errors, prefix="teacher_reference.")
    files = scenario.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
    else:
        for index, item in enumerate(files):
            if not isinstance(item, dict):
                errors.append(f"files[{index}] must be an object")
                continue
            _require_string(item, "target_relative", errors, prefix=f"files[{index}].")
            _require_string(item, "baseline", errors, prefix=f"files[{index}].")
            _validate_relative_target(item.get("target_relative"), errors, f"files[{index}].target_relative")
            if isinstance(item.get("baseline"), str) and not _resolve(base_dir, item["baseline"]).is_file():
                errors.append(f"files[{index}].baseline does not exist: {item['baseline']}")
            teacher = item.get("teacher", teacher_reference.get("file") if isinstance(teacher_reference, dict) else None)
            if isinstance(teacher, str) and not _resolve(base_dir, teacher).is_file():
                errors.append(f"files[{index}].teacher does not exist: {teacher}")
    if isinstance(teacher_reference, dict) and isinstance(teacher_reference.get("file"), str):
        if not _resolve(base_dir, teacher_reference["file"]).is_file():
            errors.append(f"teacher_reference.file does not exist: {teacher_reference['file']}")
    if isinstance(scenario.get("source_project"), str) and not _resolve(base_dir, scenario["source_project"]).is_dir():
        errors.append(f"source_project does not exist: {scenario['source_project']}")

    apply_spec = scenario.get("apply", {"type": "copy_teacher_to_fixture"})
    if not isinstance(apply_spec, dict):
        errors.append("apply must be an object")
    else:
        apply_type = apply_spec.get("type", "copy_teacher_to_fixture")
        if apply_type not in {"copy_teacher_to_fixture", "sandbox_patch_package"}:
            errors.append(f"unsupported scenario apply type: {apply_type}")
        if apply_type == "sandbox_patch_package":
            if apply_spec.get("builder") != "gigachat_sandbox_patch":
                errors.append(f"unsupported sandbox patch builder: {apply_spec.get('builder')}")
            for key in ("write_review", "apply_approved"):
                if key in apply_spec and not isinstance(apply_spec[key], bool):
                    errors.append(f"apply.{key} must be a boolean")

    optional_files = scenario.get("optional_files", [])
    if not isinstance(optional_files, list) or not all(isinstance(path, str) for path in optional_files):
        errors.append("optional_files must be a list of strings")
    comparisons = scenario.get("comparisons", [])
    if comparisons and not isinstance(comparisons, list):
        errors.append("comparisons must be a list")
    elif isinstance(comparisons, list):
        _validate_comparisons(comparisons, errors)
    feature_needles = scenario.get("feature_needles", [])
    if not isinstance(feature_needles, list):
        errors.append("feature_needles must be a list")
    elif feature_needles:
        _validate_feature_needles(feature_needles, errors, "feature_needles")
    return {"status": "ok" if not errors else "failed", "errors": errors}


def _apply_scenario(*, base_dir: Path, fixture: Path, scenario: dict[str, Any], root: Path, write: bool) -> dict[str, Any]:
    apply_spec = dict(scenario.get("apply", {}))
    apply_type = apply_spec.get("type", "copy_teacher_to_fixture")
    if apply_type == "copy_teacher_to_fixture":
        for item in scenario.get("files", []):
            teacher = _resolve(base_dir, item.get("teacher", scenario["teacher_reference"]["file"]))
            target = fixture / str(item["target_relative"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(teacher, target)
        return {"target": "fixture", "status": "applied", "source_project_unchanged": True}
    if apply_type == "sandbox_patch_package":
        return _apply_sandbox_patch_package(fixture=fixture, root=root, apply_spec=apply_spec, write=write)
    raise ValueError(f"unsupported scenario apply type: {apply_type}")


def _apply_sandbox_patch_package(*, fixture: Path, root: Path, apply_spec: dict[str, Any], write: bool) -> dict[str, Any]:
    builder = apply_spec.get("builder")
    if builder != "gigachat_sandbox_patch":
        raise ValueError(f"unsupported sandbox patch builder: {builder}")
    from tools.gigachat_sandbox_patch import build_patch
    from tools.sandbox_patch_review import review_patch_package

    package = build_patch(root=root, project_dir=fixture, target_model=str(apply_spec.get("target_model", "GigaChat-2-Pro")))
    review = review_patch_package(
        patch_dir=Path(str(package["sandbox_dir"])),
        expected_source_project=fixture,
        write_review=bool(apply_spec.get("write_review", write)),
        apply_approved=bool(apply_spec.get("apply_approved", True)),
    )
    return {
        "target": "fixture",
        "status": review.get("apply", {}).get("status", review.get("status")),
        "source_project_unchanged": True,
        "package": {
            "status": package.get("status"),
            "sandbox_dir": package.get("sandbox_dir"),
            "verification": dict(package.get("verification", {})).get("status"),
        },
        "review": {
            "status": review.get("status"),
            "apply_status": dict(review.get("apply", {})).get("status"),
            "validation": review.get("validation"),
            "risk_summary": review.get("risk_summary"),
        },
    }


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
        (item.get("exact_match") is True or item.get("exact_match_required") is False)
        and item.get("feature_score") == item.get("feature_total")
        for item in comparisons
    )


def _comparison_with_policy(
    *,
    teacher_path: Path,
    result_path: Path,
    feature_needles: list[FeatureNeedle],
    exact_match_required: bool,
) -> dict[str, Any]:
    comparison = compare_text_files(teacher_path=teacher_path, result_path=result_path, feature_needles=feature_needles)
    comparison["exact_match_required"] = exact_match_required
    return comparison


def _resolve(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _snapshot_project(project_dir: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(item for item in project_dir.rglob("*") if item.is_file()):
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        snapshot[path.relative_to(project_dir).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _require_string(mapping: dict[str, Any], key: str, errors: list[str], *, prefix: str = "") -> None:
    if not isinstance(mapping.get(key), str) or not str(mapping.get(key)).strip():
        errors.append(f"{prefix}{key} must be a non-empty string")


def _validate_relative_target(value: Any, errors: list[str], field: str) -> None:
    if not isinstance(value, str):
        return
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{field} must be a safe relative path")


def _validate_comparisons(comparisons: list[Any], errors: list[str]) -> None:
    for index, item in enumerate(comparisons):
        if not isinstance(item, dict):
            errors.append(f"comparisons[{index}] must be an object")
            continue
        _require_string(item, "target_relative", errors, prefix=f"comparisons[{index}].")
        _validate_relative_target(item.get("target_relative"), errors, f"comparisons[{index}].target_relative")
        if "exact_match_required" in item and not isinstance(item["exact_match_required"], bool):
            errors.append(f"comparisons[{index}].exact_match_required must be a boolean")
        features = item.get("features", [])
        if not isinstance(features, list):
            errors.append(f"comparisons[{index}].features must be a list")
            continue
        _validate_feature_needles(features, errors, f"comparisons[{index}].features")


def _validate_feature_needles(features: list[Any], errors: list[str], prefix: str) -> None:
    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(f"{prefix}[{feature_index}] must be an object")
            continue
        _require_string(feature, "name", errors, prefix=f"{prefix}[{feature_index}].")
        for key in ("present", "absent"):
            values = feature.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                errors.append(f"{prefix}[{feature_index}].{key} must be a list of strings")

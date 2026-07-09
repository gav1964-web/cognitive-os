"""Reusable teacher-reference project change trial helpers."""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrialFile:
    """A source file copied into the isolated trial fixture."""

    target_relative: str
    baseline_path: Path


@dataclass(frozen=True)
class FeatureNeedle:
    """Text evidence expected in, or absent from, a trial result."""

    name: str
    present: tuple[str, ...] = field(default_factory=tuple)
    absent: tuple[str, ...] = field(default_factory=tuple)


def create_trial_dir(root: Path, artifact_group: str, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / "artifacts" / artifact_group / f"{label}_{stamp}"


def create_fixture(out_dir: Path, fixture_name: str, files: list[TrialFile]) -> Path:
    fixture = out_dir / fixture_name
    fixture.mkdir(parents=True, exist_ok=True)
    for item in files:
        target = fixture / item.target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.baseline_path, target)
    return fixture


def copy_optional_files(source_project: Path, fixture: Path, relative_paths: list[str]) -> list[str]:
    copied: list[str] = []
    for relative in relative_paths:
        source = source_project / relative
        if source.is_file():
            target = fixture / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative)
    return copied


def compare_text_files(
    *,
    teacher_path: Path,
    result_path: Path,
    feature_needles: list[FeatureNeedle],
    diff_limit: int = 80,
) -> dict[str, Any]:
    teacher = normalize_text(teacher_path.read_text(encoding="utf-8"))
    result = normalize_text(result_path.read_text(encoding="utf-8"))
    features = {
        needle.name: all(value in result for value in needle.present)
        and all(value not in result for value in needle.absent)
        for needle in feature_needles
    }
    diff = list(difflib.unified_diff(teacher.splitlines(), result.splitlines(), fromfile="teacher", tofile="trial", lineterm=""))
    return {
        "teacher_file": teacher_path.as_posix(),
        "result_file": result_path.as_posix(),
        "exact_match": teacher == result,
        "feature_score": sum(1 for ok in features.values() if ok),
        "feature_total": len(features),
        "features": features,
        "diff_lines": len(diff),
        "diff_head": diff[:diff_limit],
    }


def build_trial_report(
    *,
    artifact_type: str,
    status: str,
    source_project: Path,
    trial_fixture: Path,
    teacher_file: Path,
    baseline_sources: list[Path],
    sections: dict[str, Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "artifact_type": artifact_type,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project": source_project.as_posix(),
        "baseline_sources": [path.as_posix() for path in baseline_sources],
        "teacher_reference": {
            "kind": "external_teacher_corrector_patch",
            "quality": "teacher_reference_not_ground_truth",
            "file": teacher_file.as_posix(),
        },
        "trial_fixture": trial_fixture.as_posix(),
        "invariants": trial_invariants(),
    }
    report.update(sections)
    return report


def trial_invariants() -> dict[str, bool]:
    return {
        "source_project_modified": False,
        "fixture_only_apply": True,
        "teacher_reference_is_ground_truth": False,
        "automatic_code_changes_from_own_output": False,
    }


def write_report(report: dict[str, Any], out_dir: Path, filename: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"

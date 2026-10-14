"""Freeze and run a train/holdout foundation self-improvement exam."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.role_foundation_field_trial import run_role_foundation_field_trial
from runtime.self_improvement_engine_fingerprint import improvement_engine_fingerprint
from runtime.self_improvement_iteration import (
    assess_iteration,
    capture_promotion_state,
    changed_promotion_paths,
    rollback_promotion_state,
    snapshot_digest,
)
from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial
from tools.foundation_transfer_checkpoint import (
    checkpoint_path, load_checkpoint, load_reports, save_checkpoint,
)
from tools.self_improvement_project_discovery import holdout_discoverer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "run"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--seed", default="foundation-transfer-v1")
    parser.add_argument("--holdout-per-stratum", type=int, default=2)
    parser.add_argument("--target-score", type=float, default=9.7)
    parser.add_argument("--max-training-projects", type=int, default=3)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    corpus = _resolve(root, args.corpus_dir)
    if args.phase == "freeze":
        report = freeze_exam(
            root, corpus, seed=args.seed,
            holdout_per_stratum=args.holdout_per_stratum,
        )
    else:
        report = run_exam(
            root, corpus, target_score=args.target_score,
            max_training_projects=args.max_training_projects,
            max_iterations=args.max_iterations,
            resume=args.resume,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"frozen", "transfer_verified"} else 1


def freeze_exam(
    root: Path, corpus: Path, *, seed: str, holdout_per_stratum: int,
) -> dict[str, Any]:
    manifest_path = corpus / "transfer_exam.json"
    if manifest_path.exists():
        raise RuntimeError("transfer exam is already frozen")
    selection_path = corpus / "selection.json"
    clone_path = corpus / "clone_report.json"
    selection = _read_json(selection_path)
    clone = _read_json(clone_path)
    if selection.get("selection_frozen") is not True or clone.get("status") != "ok":
        raise RuntimeError("frozen selection and successful clone report are required")
    projects = _freeze_projects(corpus, selection, seed, holdout_per_stratum)
    payload = {
        "artifact_type": "FoundationTransferExamManifest",
        "schema_version": "foundation_transfer_exam.v1",
        "status": "frozen",
        "created_at": _now(),
        "seed": seed,
        "holdout_per_stratum": holdout_per_stratum,
        "selection_sha256": _file_digest(selection_path),
        "source_commit": _git_output(root, "rev-parse", "HEAD"),
        "engine_fingerprint": improvement_engine_fingerprint(root),
        "promotion_snapshot_sha256": snapshot_digest(capture_promotion_state(root)),
        "projects": projects,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return {**payload, "manifest_path": manifest_path.as_posix(), "summary": _split_summary(projects)}


def run_exam(
    root: Path, corpus: Path, *, target_score: float,
    max_training_projects: int, max_iterations: int | None,
    trainer: Callable[..., dict[str, Any]] = run_self_improving_foundation_trial,
    resume: bool = False,
) -> dict[str, Any]:
    manifest_path = corpus / "transfer_exam.json"
    result_path = corpus / "transfer_exam_result.json"
    if result_path.exists():
        raise RuntimeError("transfer exam result already exists")
    manifest = _read_json(manifest_path)
    checkpoint = load_checkpoint(corpus, manifest_path)
    if checkpoint and not resume:
        raise RuntimeError("transfer exam checkpoint exists; pass --resume")
    if resume and not checkpoint:
        raise RuntimeError("transfer exam checkpoint is missing")
    if checkpoint and not checkpoint.get("resume_allowed"):
        raise RuntimeError(str(checkpoint.get("reason") or "transfer exam resume is blocked"))
    expected_snapshot = str(
        checkpoint.get("promotion_snapshot_sha256") if checkpoint
        else manifest.get("promotion_snapshot_sha256")
    )
    _verify_frozen_state(root, corpus, manifest, expected_snapshot)
    reports = load_reports(checkpoint) if checkpoint else {}
    promotion_changes = list(checkpoint.get("promotion_paths_changed") or [])
    train = _paths(corpus, manifest, "train")
    holdout = _paths(corpus, manifest, "holdout")
    before_snapshot = capture_promotion_state(root)
    train_baseline = reports.get("train_baseline")
    if not train_baseline:
        _progress("train_baseline_started", len(train))
        train_baseline = _measure(root, train, target_score)
        reports["train_baseline"] = train_baseline
        _checkpoint(root, corpus, manifest_path, "train_baseline_completed", reports)
    holdout_baseline = reports.get("holdout_baseline")
    if not holdout_baseline:
        _progress("sealed_holdout_baseline_started", len(holdout))
        holdout_baseline = _measure(root, holdout, target_score)
        reports["holdout_baseline"] = holdout_baseline
        _checkpoint(root, corpus, manifest_path, "holdout_baseline_completed", reports)
    training = reports.get("training")
    if not training:
        _progress("autonomous_training_started", len(train))
        training_snapshot = capture_promotion_state(root)
        try:
            training = trainer(
                root=root, project_roots=train, target_score=target_score,
                max_training_projects=max_training_projects, max_iterations=max_iterations,
                write=True, executable_acceptance=True,
                _holdout_discoverer=holdout_discoverer(root), _progress=_training_progress,
            )
        except BaseException:
            rollback_promotion_state(root, training_snapshot)
            save_checkpoint(
                corpus, manifest_path, stage="training_interrupted",
                promotion_snapshot_sha256=snapshot_digest(training_snapshot),
                reports=reports, resume_allowed=False,
                reason="training_stage_interrupted_restart_required",
            )
            raise
        reports["training"] = training
        promotion_changes = changed_promotion_paths(root, before_snapshot)
        _checkpoint(
            root, corpus, manifest_path, "training_completed", reports,
            metadata={"promotion_paths_changed": promotion_changes},
        )
    _progress("sealed_holdout_verification_started", len(holdout))
    holdout_final = _measure(root, holdout, target_score)
    assessment = assess_iteration(holdout_baseline, holdout_final, target_score=target_score)
    final_minimum = float(dict(holdout_final.get("summary") or {}).get("project_min_score") or 0.0)
    verified = (
        final_minimum >= target_score
        and not assessment["regressions"]
        and holdout_final.get("status") == "ok"
    )
    result = {
        "artifact_type": "FoundationTransferExamResult",
        "schema_version": "foundation_transfer_exam_result.v1",
        "status": "transfer_verified" if verified else "transfer_not_verified",
        "created_at": _now(),
        "target_score": target_score,
        "manifest_sha256": _file_digest(manifest_path),
        "engine_fingerprint_before": manifest["engine_fingerprint"],
        "engine_fingerprint_after": improvement_engine_fingerprint(root),
        "promotion_paths_changed": promotion_changes,
        "train_baseline": _report_reference(train_baseline),
        "holdout_baseline": _report_reference(holdout_baseline),
        "training": _training_reference(training),
        "holdout_final": _report_reference(holdout_final),
        "holdout_assessment": assessment,
        "critical_intervention": training.get("critical_intervention"),
        "invariants": {
            "holdout_excluded_from_training": not set(train) & set(holdout),
            "frozen_manifest": True,
            "manual_failure_repair_during_exam": False,
        },
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    checkpoint_path(corpus).unlink(missing_ok=True)
    return {**result, "result_path": result_path.as_posix()}


def _freeze_projects(
    corpus: Path, selection: dict[str, Any], seed: str, holdout_count: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for value in selection.get("projects") or []:
        row = dict(value)
        grouped.setdefault(str(row.get("stratum") or "unknown"), []).append(row)
    frozen = []
    for stratum, rows in sorted(grouped.items()):
        if holdout_count < 1 or len(rows) <= holdout_count:
            raise ValueError(f"invalid holdout size for {stratum}")
        ranked = sorted(rows, key=lambda row: _partition_key(seed, str(row["full_name"])))
        holdout_names = {str(row["full_name"]) for row in ranked[:holdout_count]}
        for row in sorted(rows, key=lambda item: str(item["full_name"]).lower()):
            path = corpus / "src" / str(row["full_name"]).replace("/", "__")
            frozen.append({
                "full_name": row["full_name"], "stratum": stratum,
                "partition": "holdout" if row["full_name"] in holdout_names else "train",
                "path": path.relative_to(corpus).as_posix(),
                "commit": _git_output(path, "rev-parse", "HEAD"),
            })
    return frozen


def _verify_frozen_state(
    root: Path, corpus: Path, manifest: dict[str, Any], expected_snapshot: str,
) -> None:
    if manifest.get("status") != "frozen":
        raise RuntimeError("transfer exam manifest is not frozen")
    if improvement_engine_fingerprint(root) != manifest.get("engine_fingerprint"):
        raise RuntimeError("self-improvement engine changed after exam freeze")
    if snapshot_digest(capture_promotion_state(root)) != expected_snapshot:
        raise RuntimeError("promotion state changed after exam freeze")
    for row in manifest.get("projects") or []:
        path = corpus / str(row["path"])
        if _git_output(path, "rev-parse", "HEAD") != row.get("commit"):
            raise RuntimeError(f"project commit changed after freeze: {row.get('full_name')}")


def _measure(root: Path, projects: list[Path], target: float) -> dict[str, Any]:
    return run_role_foundation_field_trial(
        root=root, project_roots=projects, target_score=target,
        write=True, executable_acceptance=True,
    )


def _paths(corpus: Path, manifest: dict[str, Any], partition: str) -> list[Path]:
    return [
        corpus / str(row["path"]) for row in manifest.get("projects") or []
        if row.get("partition") == partition
    ]


def _report_reference(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"), "report_path": report.get("report_path"),
        "summary": report.get("summary"),
    }


def _training_reference(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": report.get("status"), "report_path": report.get("report_path"),
        "summary": report.get("summary"),
    }


def _checkpoint(
    root: Path, corpus: Path, manifest_path: Path, stage: str,
    reports: dict[str, dict[str, Any]], metadata: dict[str, Any] | None = None,
) -> None:
    save_checkpoint(
        corpus, manifest_path, stage=stage,
        promotion_snapshot_sha256=snapshot_digest(capture_promotion_state(root)),
        reports=reports, metadata=metadata,
    )


def _split_summary(projects: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "project_count": len(projects),
        "train_count": sum(row["partition"] == "train" for row in projects),
        "holdout_count": sum(row["partition"] == "holdout" for row in projects),
        "strata": sorted({str(row["stratum"]) for row in projects}),
    }


def _partition_key(seed: str, name: str) -> str:
    return hashlib.sha256(f"{seed}:{name.lower()}".encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={path.as_posix()}", "-C", str(path), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-500:])
    return result.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _progress(stage: str, project_count: int) -> None:
    print(json.dumps({"transfer_exam_progress": {"stage": stage, "project_count": project_count}}), file=sys.stderr, flush=True)


def _training_progress(event: dict[str, Any]) -> None:
    print(json.dumps({"transfer_exam_training": event}), file=sys.stderr, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())

"""Manage frozen direct/short/full Cognitive OS evaluation evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--output", default="evaluation/protocol_v2_manifest.json")
    freeze.add_argument("tasks", nargs="*")
    status = subparsers.add_parser("status")
    status.add_argument("--manifest", default="evaluation/protocol_v2_manifest.json")
    status.add_argument("--receipts", default="artifacts/evaluation_v2/receipts")
    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--manifest", default="evaluation/protocol_v2_manifest.json")
    bundle.add_argument("--receipts", default="artifacts/evaluation_v2/receipts")
    bundle.add_argument("--output-dir", default="artifacts/evaluation_v2/blind")
    score = subparsers.add_parser("score")
    score.add_argument("--bundle", required=True)
    score.add_argument("--key", required=True)
    score.add_argument("--scorecard", required=True)
    score.add_argument("--receipts", default="artifacts/evaluation_v2/receipts")
    score.add_argument("--output", default="artifacts/evaluation_v2/report.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    policy = _read(root / "config" / "evaluation_protocol_v2.json")
    if args.command == "freeze":
        return _freeze(root, args, policy)
    if args.command == "status":
        return _status(root, args, policy)
    if args.command == "bundle":
        return _bundle(root, args, policy)
    return _score(root, args, policy)


def _freeze(root: Path, args: argparse.Namespace, policy: dict[str, Any]) -> int:
    from runtime.three_route_evaluation import freeze_manifest, protocol_status

    manifest = freeze_manifest(root, source_commit=_commit(root), task_names=args.tasks or None)
    output = _path(root, args.output)
    _write(output, manifest)
    result = {
        "manifest": output.as_posix(),
        "task_count": len(manifest["tasks"]),
        "manifest_digest": manifest["manifest_digest"],
        "status": protocol_status(manifest, [], policy),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _status(root: Path, args: argparse.Namespace, policy: dict[str, Any]) -> int:
    from runtime.three_route_evaluation import load_receipts, protocol_status

    result = protocol_status(
        _read(_path(root, args.manifest)), load_receipts(_path(root, args.receipts)), policy
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready_for_blind_judging" else 2


def _bundle(root: Path, args: argparse.Namespace, policy: dict[str, Any]) -> int:
    from runtime.three_route_evaluation import build_blind_bundle, load_receipts

    manifest = _read(_path(root, args.manifest))
    blind, key = build_blind_bundle(manifest, load_receipts(_path(root, args.receipts)), policy)
    output = _path(root, args.output_dir)
    _write(output / "bundle.json", blind)
    _write(output / "blind_key.json", key)
    print(json.dumps({"status": "ok", "bundle_digest": blind["bundle_digest"], "output_dir": output.as_posix()}, indent=2))
    return 0


def _score(root: Path, args: argparse.Namespace, policy: dict[str, Any]) -> int:
    from runtime.three_route_evaluation import load_receipts
    from runtime.three_route_evaluation_scoring import score_blind_evaluation

    report = score_blind_evaluation(
        bundle=_read(_path(root, args.bundle)),
        blind_key=_read(_path(root, args.key)),
        scorecard=_read(_path(root, args.scorecard)),
        receipts=load_receipts(_path(root, args.receipts)),
        policy=policy,
    )
    _write(_path(root, args.output), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "evaluated" else 2


def _commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

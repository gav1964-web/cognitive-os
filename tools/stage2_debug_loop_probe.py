"""Exercise the Stage 2 debug loop against intentionally damaged packages."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.greenfield_scaffold import create_greenfield_scaffold, run_project_verification
from runtime.greenfield_templates import acceptance_covered
from runtime.programmer_project_review import review_programmer_project
from runtime.stage2_debug_loop import run_stage2_debug_loop


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--case",
        choices=["fastapi_csv_aggregator", "fastapi_kv_store", "text_stats_cli"],
        default="fastapi_kv_store",
    )
    parser.add_argument("--curriculum-dir", default="curricula/programmer_prompt_stage2")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    reference = _load_reference(root / args.curriculum_dir, args.case)
    scaffold = create_greenfield_scaffold(root=root, case_name=args.case, reference=reference)
    damage = _damage_package(Path(scaffold["project_dir"]), args.case)
    scaffold["verification"] = run_project_verification(Path(scaffold["project_dir"]))
    scaffold["acceptance_covered"] = acceptance_covered(args.case, scaffold["verification"])
    tester_review = review_programmer_project(scaffold=scaffold, reference=reference)
    review_run = {"status": "needs_rework", "programmer_artifact": scaffold, "tester_review": tester_review}
    loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
    report = {
        "artifact_type": "Stage2DebugLoopProbe",
        "status": "ok" if loop.get("final_status") == "ok" else "needs_rework",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "damage": damage,
        "debug_loop": loop,
        "invariants": {
            "sandbox_only": True,
            "source_tree_changes": False,
            "registry_changes": False,
            "bounded_rework": True,
        },
    }
    if args.write:
        report["report_path"] = _write_report(root, report).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def _load_reference(curriculum_dir: Path, case_name: str) -> dict:
    return json.loads((curriculum_dir / case_name / "teacher_reference.json").read_text(encoding="utf-8"))


def _damage_package(project_dir: Path, case_name: str) -> dict[str, str]:
    if case_name == "fastapi_csv_aggregator":
        return _damage_csv(project_dir)
    if case_name == "text_stats_cli":
        return _damage_text_stats_cli(project_dir)
    return _damage_kv(project_dir)


def _damage_csv(project_dir: Path) -> dict[str, str]:
    path = project_dir / "src" / "csv_aggregator_service" / "app.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("from fastapi import FastAPI, HTTPException\n", "from fastapi import FastAPI\n")
    text = text.replace(
        "    try:\n"
        "        report = aggregate_csv(payload.csv_text)\n"
        "    except ValueError as exc:\n"
        "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n",
        "    report = aggregate_csv(payload.csv_text)\n",
    )
    path.write_text(text, encoding="utf-8")
    return {"kind": "removed_controlled_400", "path": "src/csv_aggregator_service/app.py"}


def _damage_kv(project_dir: Path) -> dict[str, str]:
    path = project_dir / "src" / "kv_store_service" / "app.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("from fastapi import FastAPI, HTTPException\n", "from fastapi import FastAPI\n")
    text = text.replace(
        "    item = store.get(key)\n"
        "    if item is None:\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return item\n",
        "    item = store.get(key)\n    return item\n",
    )
    text = text.replace(
        "    if not store.delete(key):\n"
        "        raise HTTPException(status_code=404, detail='item not found')\n"
        "    return {'status': 'deleted', 'key': key}\n",
        "    store.delete(key)\n    return {'status': 'deleted', 'key': key}\n",
    )
    path.write_text(text, encoding="utf-8")
    return {"kind": "removed_controlled_404", "path": "src/kv_store_service/app.py"}


def _damage_text_stats_cli(project_dir: Path) -> dict[str, str]:
    path = project_dir / "src" / "text_stats" / "cli.py"
    path.write_text(
        "from __future__ import annotations\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    return 0\n",
        encoding="utf-8",
    )
    return {"kind": "removed_cli_input_output_contract", "path": "src/text_stats/cli.py"}


def _write_report(root: Path, report: dict) -> Path:
    out_dir = root / "artifacts" / "stage2_debug_loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"{report['case']}_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

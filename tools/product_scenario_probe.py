"""Probe Stage 3 product-scenario drift boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TEXT_STATS_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, "
    "считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты."
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.product_debug_loop import run_product_debug_loop
    from runtime.verified_system_package import build_verified_system_package

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--damage", choices=["core_behavior"], default="core_behavior")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = root / "curricula" / "programmer_prompt_stage2"
    package = build_verified_system_package(root=root, prompt=TEXT_STATS_PROMPT, curriculum_dir=curriculum_dir, write=args.write)
    reference = json.loads((curriculum_dir / "text_stats_cli" / "teacher_reference.json").read_text(encoding="utf-8"))
    damage = _damage_core_behavior(package)
    loop = run_product_debug_loop(package=package, reference=reference, max_attempts=1)
    first = dict(loop["attempts"][0]) if loop.get("attempts") else {}
    analysis = dict(first.get("failure_analysis", {}))
    report = {
        "artifact_type": "ProductScenarioProbe",
        "status": "ok" if loop["final_status"] == "needs_rework" and analysis.get("blockers") == ["core_behavior_drift"] else "failed",
        "damage": args.damage,
        "damage_detail": damage,
        "debug_loop": loop,
        "expected_boundary": "controlled_block_for_core_behavior_drift",
        "invariants": loop["invariants"],
    }
    if args.write:
        report["report_path"] = _write_report(root, report, args.damage).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def _damage_core_behavior(package: dict[str, object]) -> dict[str, str]:
    project_dir = Path(str(package.get("project_dir") or ""))
    stats_path = project_dir / "src" / "text_stats" / "stats.py"
    text = stats_path.read_text(encoding="utf-8")
    stats_path.write_text(text.replace("'words': len(text.split())", "'words': 0"), encoding="utf-8")
    package["verification_report"] = {"status": "failed"}
    _mark_checks(package, {"verification_passed": False})
    return {"file": stats_path.as_posix(), "kind": "wrong_word_count"}


def _mark_checks(package: dict[str, object], values: dict[str, bool]) -> None:
    tester = dict(package.get("tester_review", {}))
    checks = dict(tester.get("checks", {}))
    checks.update(values)
    tester["checks"] = checks
    package["tester_review"] = tester


def _write_report(root: Path, report: dict[str, object], damage: str) -> Path:
    out_dir = root / "artifacts" / "product_scenario_probes"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"product_scenario_{damage}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

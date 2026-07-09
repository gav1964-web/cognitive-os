"""Probe executable Stage 3 product debug loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


KV_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
    "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
    "README, тесты и команду запуска."
)
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
    parser.add_argument(
        "--damage",
        choices=["documentation", "scenario", "api_contract", "cli_ux", "readme_api"],
        default="documentation",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    curriculum_dir = root / "curricula" / "programmer_prompt_stage2"
    case_name, prompt = _case_for_damage(args.damage)
    package = build_verified_system_package(root=root, prompt=prompt, curriculum_dir=curriculum_dir, write=args.write)
    reference = _reference(curriculum_dir, case_name)
    _damage(package, args.damage)
    loop = run_product_debug_loop(package=package, reference=reference, max_attempts=1)
    report = {
        "artifact_type": "ProductDebugLoopProbe",
        "status": "ok" if loop["final_status"] == "ok" else "failed",
        "damage": args.damage,
        "debug_loop": loop,
        "invariants": loop["invariants"],
    }
    if args.write:
        report["report_path"] = _write_report(root, report, args.damage).as_posix()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def _case_for_damage(damage: str) -> tuple[str, str]:
    if damage == "cli_ux":
        return "text_stats_cli", TEXT_STATS_PROMPT
    return "fastapi_kv_store", KV_PROMPT


def _reference(curriculum_dir: Path, case_name: str) -> dict[str, object]:
    path = curriculum_dir / case_name / "teacher_reference.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _damage(package: dict[str, object], damage: str) -> None:
    if damage == "documentation":
        package["documentation"] = {"readme": None, "run_instructions": [], "verification_summary": None}
    elif damage == "scenario":
        tests = dict(package.get("tests", {}))
        tests["covered_acceptance"] = []
        package["tests"] = tests
    elif damage == "api_contract":
        app_path = Path(str(package.get("project_dir") or "")) / "src" / "kv_store_service" / "app.py"
        text = app_path.read_text(encoding="utf-8")
        app_path.write_text(text.replace("@app.get('/items/{key}')", "@app.get('/broken/{key}')"), encoding="utf-8")
        package["verification_report"] = {"status": "failed"}
        tester = dict(package.get("tester_review", {}))
        checks = dict(tester.get("checks", {}))
        checks["verification_passed"] = False
        tester["checks"] = checks
        package["tester_review"] = tester
    elif damage == "cli_ux":
        cli_path = Path(str(package.get("project_dir") or "")) / "src" / "text_stats" / "cli.py"
        cli_path.write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
        package["verification_report"] = {"status": "failed"}
        _mark_checks(package, {"has_cli_entrypoint": False, "cli_uses_argparse": False, "cli_accepts_input_output": False})
    else:
        readme_path = Path(str(package.get("project_dir") or "")) / "README.md"
        readme_path.write_text("# Wrong service\n\nRun app: `uvicorn wrong.app:app --app-dir src`.\n", encoding="utf-8")
        _mark_checks(package, {"readme_behavior_aligned": False, "readme_has_run_command": False, "readme_mentions_prompt": False})


def _mark_checks(package: dict[str, object], values: dict[str, bool]) -> None:
    tester = dict(package.get("tester_review", {}))
    checks = dict(tester.get("checks", {}))
    checks.update(values)
    tester["checks"] = checks
    package["tester_review"] = tester


def _write_report(root: Path, report: dict[str, object], damage: str) -> Path:
    out_dir = root / "artifacts" / "product_debug_loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"product_debug_loop_{damage}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

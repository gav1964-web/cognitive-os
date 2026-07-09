"""Run a small Stage 3 product-slice benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CASES = [
    {
        "name": "fastapi_kv_store",
        "curriculum": "curricula/programmer_prompt_stage2",
        "prompt": (
            "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
            "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
            "README, тесты и команду запуска."
        ),
    },
    {
        "name": "fastapi_csv_aggregator",
        "curriculum": "curricula/programmer_prompt_stage2",
        "prompt": (
            "Сделай локальную FastAPI-службу с зависимостью fastapi, которая принимает CSV, "
            "валидирует колонки category/value, считает агрегаты по category, сохраняет JSON-отчёт, "
            "имеет README, тесты и команду запуска."
        ),
    },
    {
        "name": "text_stats_cli",
        "curriculum": "curricula/programmer_prompt_stage2",
        "prompt": (
            "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, "
            "считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты."
        ),
    },
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from runtime.product_slice import build_product_slice_spec

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    cases = []
    for case in CASES:
        report = build_product_slice_spec(
            root=root,
            prompt=case["prompt"],
            curriculum_dir=root / case["curriculum"],
            write=args.write,
        )
        cases.append(_case_summary(case["name"], report))
    summary = {
        "case_count": len(cases),
        "ok": sum(1 for case in cases if case["status"] == "ok"),
        "failed": sum(1 for case in cases if case["status"] != "ok"),
    }
    payload = {
        "artifact_type": "ProductSliceBenchmark",
        "status": "ok" if summary["failed"] == 0 else "needs_review",
        "summary": summary,
        "cases": cases,
        "invariants": {
            "direct_user_source_modification": False,
            "sandbox_only": True,
            "stage2_package_is_execution_engine": True,
        },
    }
    if args.write:
        payload["report_path"] = _write_report(root, payload).as_posix()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


def _case_summary(name: str, report: dict[str, object]) -> dict[str, object]:
    return {
        "name": name,
        "status": report.get("status"),
        "system_type": dict(report.get("scope", {})).get("system_type"),
        "release_decision": dict(report.get("release_decision", {})).get("decision"),
        "requirements": dict(report.get("requirements", {})).get("status"),
        "task_graph": dict(report.get("task_graph", {})).get("status"),
        "documentation_review": dict(report.get("documentation_review", {})).get("status"),
        "scenario_verification": dict(report.get("scenario_verification", {})).get("status"),
        "product_debug_loop": dict(report.get("product_debug_loop", {})).get("status"),
        "product_slice_path": report.get("product_slice_path"),
    }


def _write_report(root: Path, payload: dict[str, object]) -> Path:
    out_dir = root / "artifacts" / "product_slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "product_slice_benchmark.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

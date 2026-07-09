"""Stage 3 acceptance gates."""

from __future__ import annotations

import sys

import mvp_acceptance_programmer_checks as programmer_checks


STAGE3_PRODUCT_SLICE_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
    "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
    "README, тесты и команду запуска."
)


def stage3_checks(report) -> None:
    report.command(
        "product_slice_spec",
        [
            sys.executable,
            "tools/product_slice.py",
            "--root",
            ".",
            "--curriculum-dir",
            "curricula/programmer_prompt_stage2",
            "--prompt",
            STAGE3_PRODUCT_SLICE_PROMPT,
            "--write",
        ],
        layers=["L4"],
        check=programmer_checks.product_slice_ok,
    )
    report.command(
        "product_debug_loop_probe",
        [
            sys.executable,
            "tools/product_debug_loop_probe.py",
            "--root",
            ".",
            "--damage",
            "api_contract",
            "--write",
        ],
        layers=["L4"],
        check=programmer_checks.product_debug_loop_probe_ok,
    )
    report.command(
        "product_debug_loop_cli_ux_probe",
        [
            sys.executable,
            "tools/product_debug_loop_probe.py",
            "--root",
            ".",
            "--damage",
            "cli_ux",
            "--write",
        ],
        layers=["L4"],
        check=programmer_checks.product_debug_loop_probe_ok,
    )
    report.command(
        "product_debug_loop_readme_api_probe",
        [
            sys.executable,
            "tools/product_debug_loop_probe.py",
            "--root",
            ".",
            "--damage",
            "readme_api",
            "--write",
        ],
        layers=["L4"],
        check=programmer_checks.product_debug_loop_probe_ok,
    )
    report.command(
        "product_slice_benchmark",
        [sys.executable, "tools/product_slice_benchmark.py", "--root", ".", "--write"],
        layers=["L4"],
        check=programmer_checks.product_slice_benchmark_ok,
    )
    report.command(
        "product_scenario_core_behavior_probe",
        [
            sys.executable,
            "tools/product_scenario_probe.py",
            "--root",
            ".",
            "--damage",
            "core_behavior",
            "--write",
        ],
        layers=["L4"],
        check=programmer_checks.product_scenario_probe_ok,
    )

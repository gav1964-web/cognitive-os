from __future__ import annotations

from pathlib import Path

from runtime.interpreter_coverage_audit import run_interpreter_coverage_audit


def test_audit_reports_transition_module_without_authority_call(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "covered.py").write_text(
        "from x import build_interpreter_decision\nnext_action = build_interpreter_decision()\n",
        encoding="utf-8",
    )
    (runtime / "gap.py").write_text("next_action = 'run'\n", encoding="utf-8")
    policy = {
        "required_modules": ["runtime/covered.py", "runtime/gap.py"],
        "authority_calls": ["build_interpreter_decision", "verify_interpreter_decision"],
        "transition_markers": ["next_action"],
        "minimum_coverage": 1.0,
        "invariants": {"report_only": True},
    }

    report = run_interpreter_coverage_audit(root=tmp_path, policy=policy)

    assert report["status"] == "coverage_gap"
    assert report["summary"]["coverage"] == 0.5
    assert report["summary"]["bypass_gap_count"] == 1


def test_repository_audit_is_explicit_about_current_coverage() -> None:
    root = Path(__file__).resolve().parents[2]
    import json
    policy = json.loads((root / "config" / "interpreter_coverage_audit.json").read_text(encoding="utf-8"))

    report = run_interpreter_coverage_audit(root=root, policy=policy)

    assert report["summary"]["transition_producer_count"] > 0
    assert report["status"] in {"passed", "coverage_gap"}
    assert report["next_action"]

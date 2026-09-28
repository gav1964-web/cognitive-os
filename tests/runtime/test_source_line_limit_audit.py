from pathlib import Path

from runtime.source_line_limit_audit import run_source_line_limit_audit


def test_source_line_limit_audit_reports_python_source_violations(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "small.py").write_text("print('ok')\n", encoding="utf-8")
    (runtime_dir / "large.py").write_text("\n".join("x = 1" for _ in range(6)) + "\n", encoding="utf-8")

    report = run_source_line_limit_audit(root=tmp_path, line_limit=5)

    assert report["status"] == "failed"
    assert report["scanned_python_file_count"] == 2
    assert report["violation_count"] == 1
    assert report["violations"][0]["path"] == "runtime/large.py"
    assert report["violations"][0]["over_by"] == 1
    assert report["violations"][0]["suggested_action"] == "extract cohesive helpers into runtime submodules"
    assert report["source_apply"] is False
    assert report["kb_promotion"] is False


def test_source_line_limit_audit_ignores_non_authoritative_generated_trees(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "ok.py").write_text("x = 1\n", encoding="utf-8")
    generated = tmp_path / "generated" / "candidates"
    generated.mkdir(parents=True)
    (generated / "large.py").write_text("\n".join("x = 1" for _ in range(10)) + "\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts" / "run"
    artifacts.mkdir(parents=True)
    (artifacts / "large.py").write_text("\n".join("x = 1" for _ in range(10)) + "\n", encoding="utf-8")
    temp = runtime_dir / ".pytest-tmp-case"
    temp.mkdir()
    (temp / "large.py").write_text("\n".join("x = 1" for _ in range(10)) + "\n", encoding="utf-8")

    report = run_source_line_limit_audit(root=tmp_path, line_limit=5)

    assert report["status"] == "passed"
    assert report["scanned_python_file_count"] == 1
    assert report["violation_count"] == 0

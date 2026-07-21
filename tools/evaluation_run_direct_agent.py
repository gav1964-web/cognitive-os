"""Run a simple direct-agent baseline for selected evaluation tasks.

This is intentionally not Cognitive OS: no L4 gates, no role artifacts, no KB
admission. It creates a minimal direct package only for tiny allowlisted prompts
and records a controlled block otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run direct-agent baseline for evaluation tasks.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("tasks", nargs="+")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rows = []
    for task_id in args.tasks:
        task_dir = root / "evaluation" / task_id
        prompt = _read_prompt(task_dir / "prompt.md")
        start = time.perf_counter()
        report = _run_direct(root=root, task_id=task_id, prompt=prompt, write=args.write)
        runtime_seconds = round(time.perf_counter() - start, 3)
        metrics_path = task_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["routes"]["direct_agent"] = _route_metrics(report, runtime_seconds)
        metrics["comparison"] = _comparison(metrics)
        metrics["verdict"] = _verdict(metrics)
        if args.write:
            metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _write_route_readme(task_dir, report)
        rows.append(
            {
                "task_id": task_id,
                "status": report.get("status"),
                "release_decision": report.get("release_decision"),
                "tests": report.get("tests", {}),
                "runtime_seconds": runtime_seconds,
            }
        )
    print(json.dumps({"artifact_type": "EvaluationDirectAgentRunReport", "status": "ok", "tasks": rows}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_direct(*, root: Path, task_id: str, prompt: str, write: bool) -> dict[str, Any]:
    lower = prompt.lower()
    if ".xls" in lower and ".png" in lower:
        return _blocked(task_id, prompt, "direct baseline has no safe .xls rendering backend without dependency policy")
    if ".xls" in lower and ".csv" in lower:
        return _blocked(task_id, prompt, "direct baseline has no safe spreadsheet round-trip backend without dependency policy")
    if "fastapi" in lower:
        return _blocked(task_id, prompt, "direct baseline does not implement local FastAPI service generation")
    if ".md" in lower and ".rtf" in lower:
        return _write_direct_package(root, task_id, prompt, "md_to_rtf", write)
    if (".jpg" in lower or ".jpeg" in lower) and ".doc" in lower:
        return _write_direct_package(root, task_id, prompt, "jpg_to_doc_html", write)
    if "верхн" in lower or "uppercase" in lower or "upper case" in lower:
        return _write_direct_package(root, task_id, prompt, "uppercase", write)
    return _blocked(task_id, prompt, "direct baseline does not recognize this prompt")


def _write_direct_package(root: Path, task_id: str, prompt: str, kind: str, write: bool) -> dict[str, Any]:
    project_dir = root / "artifacts" / "evaluation_direct_agent" / task_id
    files = ["pyproject.toml", "README.md", "src/direct_cli/__init__.py", "src/direct_cli/cli.py", "tests/test_cli.py"]
    if write:
        if project_dir.exists():
            shutil.rmtree(project_dir)
        (project_dir / "src" / "direct_cli").mkdir(parents=True, exist_ok=True)
        (project_dir / "tests").mkdir(parents=True, exist_ok=True)
        (project_dir / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n', encoding="utf-8")
        (project_dir / "README.md").write_text(f"# Direct Baseline\n\nPrompt:\n\n```text\n{prompt}\n```\n", encoding="utf-8")
        (project_dir / "src" / "direct_cli" / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "src" / "direct_cli" / "cli.py").write_text(_cli(kind), encoding="utf-8")
        (project_dir / "tests" / "test_cli.py").write_text(_tests(kind), encoding="utf-8")
        compile_result = _run([sys.executable, "-m", "compileall", "-q", "."], cwd=project_dir)
        test_result = _run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=project_dir)
    else:
        compile_result = {"status": "not_run"}
        test_result = {"status": "not_run"}
    passed = compile_result.get("status") == "passed" and test_result.get("status") == "passed"
    return {
        "artifact_type": "DirectAgentBaselineReport",
        "status": "completed" if passed else ("planned" if not write else "failed"),
        "release_decision": "completed" if passed else "blocked",
        "prompt": prompt,
        "project_dir": project_dir.as_posix(),
        "files": files,
        "verification": {"status": "passed" if passed else "not_run", "compile": compile_result, "tests": test_result},
        "tests": test_result,
        "safety": {"source_safety_violations": 0, "uses_cognitive_os": False},
    }


def _cli(kind: str) -> str:
    if kind == "uppercase":
        body = "target.write_text(source.read_text(encoding='utf-8').upper(), encoding='utf-8')"
    elif kind == "md_to_rtf":
        body = """text = source.read_text(encoding='utf-8')
    text = text.replace('\\\\', r'\\\\').replace('{', r'\\{').replace('}', r'\\}')
    lines = []
    for line in text.splitlines():
        if line.startswith('# '):
            lines.append(r'\\b ' + line[2:] + r'\\b0\\par')
        elif line:
            lines.append(line + r'\\par')
        else:
            lines.append(r'\\par')
    target.write_text(r'{\\rtf1\\ansi ' + ''.join(lines) + '}', encoding='utf-8')"""
    else:
        body = """data = source.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    target.write_text('<html><body><img src="data:image/jpeg;base64,' + encoded + '"></body></html>', encoding='utf-8')"""
    return f'''from __future__ import annotations

import argparse
import base64
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args(argv)
    source = Path(args.input)
    target = Path(args.output)
    if not source.is_file():
        parser.error(f"input file does not exist: {{source}}")
    {body}
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _tests(kind: str) -> str:
    if kind == "uppercase":
        sample = "Hello\n"
        expected = "HELLO\n"
        return f'''from pathlib import Path

from direct_cli.cli import main


def test_cli(tmp_path: Path):
    source = tmp_path / "in.txt"
    target = tmp_path / "out.txt"
    source.write_text({sample!r}, encoding="utf-8")
    assert main([str(source), str(target)]) == 0
    assert target.read_text(encoding="utf-8") == {expected!r}
'''
    if kind == "md_to_rtf":
        return '''from pathlib import Path

from direct_cli.cli import main


def test_cli(tmp_path: Path):
    source = tmp_path / "in.md"
    target = tmp_path / "out.rtf"
    source.write_text("# Title\\n\\nHello", encoding="utf-8")
    assert main([str(source), str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert text.startswith("{\\\\rtf1")
    assert "Title" in text
'''
    return '''from pathlib import Path

from direct_cli.cli import main


def test_cli(tmp_path: Path):
    source = tmp_path / "in.jpg"
    target = tmp_path / "out.doc"
    source.write_bytes(b"fake-jpeg")
    assert main([str(source), str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert "<img" in text
    assert "base64" in text
'''


def _blocked(task_id: str, prompt: str, reason: str) -> dict[str, Any]:
    return {
        "artifact_type": "DirectAgentBaselineReport",
        "status": "blocked",
        "release_decision": "blocked",
        "prompt": prompt,
        "reason": reason,
        "verification": {"status": "not_run"},
        "tests": {"status": "not_run"},
        "safety": {"source_safety_violations": 0, "uses_cognitive_os": False},
    }


def _route_metrics(report: dict[str, Any], runtime_seconds: float) -> dict[str, Any]:
    tests = dict(report.get("tests", {}))
    passed = _tests_passed(tests)
    completed = report.get("status") == "completed"
    return {
        "executor": "direct_agent_baseline",
        "model": "deterministic_direct_baseline",
        "status": "completed" if completed else "blocked",
        "requirement_coverage": 0.75 if completed else 0.2,
        "missed_requirements": 0 if completed else 1,
        "invented_requirements": 0,
        "tests_passed": passed,
        "tests_total": passed if tests.get("status") == "passed" else 0,
        "verification_status": dict(report.get("verification", {})).get("status", "not_run"),
        "repair_cycles": 0,
        "runtime_seconds": runtime_seconds,
        "estimated_cost": 0.0,
        "artifact_completeness": 0.75 if completed else 0.2,
        "source_safety_violations": 0,
        "review_blockers": 0 if completed else 1,
        "human_correction_minutes": 0,
        "release_decision": report.get("release_decision"),
        "project_dir": report.get("project_dir"),
        "block_reason": report.get("reason"),
    }


def _comparison(metrics: dict[str, Any]) -> dict[str, Any]:
    direct = dict(metrics["routes"]["direct_agent"])
    cognitive = dict(metrics["routes"]["cognitive_os"])
    if direct.get("status") == "completed" and cognitive.get("status") == "completed":
        return {
            "winner": "cognitive_os" if cognitive.get("tests_passed", 0) >= direct.get("tests_passed", 0) else "direct_agent",
            "cognitive_os_advantages": ["stronger review and safety artifacts"],
            "direct_agent_advantages": ["simpler route"],
            "no_difference": ["both routes completed"],
            "confidence": 0.45,
        }
    if cognitive.get("status") == "completed" and direct.get("status") != "completed":
        return {
            "winner": "cognitive_os",
            "cognitive_os_advantages": ["completed where direct baseline blocked"],
            "direct_agent_advantages": [],
            "no_difference": [],
            "confidence": 0.55,
        }
    return {
        "winner": "undecided",
        "cognitive_os_advantages": [],
        "direct_agent_advantages": [],
        "no_difference": ["both routes incomplete or unavailable"],
        "confidence": 0.0,
    }


def _verdict(metrics: dict[str, Any]) -> str:
    comparison = dict(metrics.get("comparison", {}))
    winner = comparison.get("winner")
    if winner == "cognitive_os":
        return "cognitive_os_wins_baseline"
    if winner == "direct_agent":
        return "direct_agent_wins"
    return "no_clear_difference" if comparison.get("confidence", 0) else "not_evaluated"


def _tests_passed(test_result: dict[str, Any]) -> int:
    stdout = str(test_result.get("stdout_tail") or "")
    if test_result.get("status") != "passed":
        return 0
    match = re.search(r"(\d+)\s+passed", stdout)
    return int(match.group(1)) if match else 1


def _run(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _read_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    markers = ("## Original Prompt", "## Prompt")
    body = ""
    for marker in markers:
        if marker in text:
            body = text.split(marker, 1)[1]
            break
    if not body:
        raise ValueError(f"prompt marker not found in {path}")
    for boundary in ("## Constraints", "## Success Criteria"):
        if boundary in body:
            body = body.split(boundary, 1)[0]
    return body.strip()


def _write_route_readme(task_dir: Path, report: dict[str, Any]) -> None:
    text = f"""# Direct Agent Baseline

Status: {report.get("status")}

Release decision: {report.get("release_decision")}

Project dir: `{report.get("project_dir")}`

Reason: {report.get("reason", "")}
"""
    (task_dir / "direct_agent" / "README.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

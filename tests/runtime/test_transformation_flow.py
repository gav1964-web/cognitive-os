from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime.extraction_proposal import _select_candidate, build_extraction_proposal
from runtime.dependency_extraction_policy import evaluate_dependency_policy
from runtime.transformation_flow import _contract_test, _main_py, run_transformation_flow


ROOT = Path(__file__).resolve().parents[2]


def test_transformation_flow_builds_tested_candidate(tmp_path):
    workspace = _copy_workspace(tmp_path)
    project_dir = workspace / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    result = run_transformation_flow(root=workspace, project_dir=project_dir, force=True)

    candidate = workspace / "generated" / "candidates" / "simple_cli_tool_normalize_text"
    assert result["status"] == "promotion_ready"
    assert result["safety"]["source_code_changes"] is False
    assert result["safety"]["registry_changes"] is False
    assert (candidate / "src" / "main.py").exists()
    assert result["dry_run_promotion"]["status"] == "dry_run_passed"
    assert not (workspace / "plugins" / "simple_cli_tool_normalize_text").exists()


def test_project_transform_cli_outputs_report(tmp_path):
    workspace = _copy_workspace(tmp_path)
    tool = workspace / "tools" / "project_transform.py"

    result = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--root",
            str(workspace),
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--force",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "promotion_ready"
    assert Path(payload["report_path"]).exists()
    assert Path(payload["candidate_path"]).exists()


def test_transformation_flow_handles_list_of_dict_sample_input(tmp_path):
    workspace = _copy_workspace(tmp_path)
    project_dir = workspace / "benchmarks" / "project_analyzer" / "projects" / "data_pipeline_csv_json"

    result = run_transformation_flow(root=workspace, project_dir=project_dir, force=True)

    assert result["status"] == "promotion_ready"
    assert result["selected"]["capability"] == "pipeline.py:normalize_rows"
    assert result["dry_run_promotion"]["status"] == "dry_run_passed"
    quality_gate = json.loads(result["dry_run_promotion"]["quality_gate"])
    assert quality_gate["sample_input"] == {"rows": [{"value": " Sample "}]}
    assert quality_gate["expected_output"] == {"result": [{"value": "sample"}]}


def test_transformation_flow_handles_tuple_output_as_jsonable_array(tmp_path):
    workspace = _copy_workspace(tmp_path)
    project_dir = workspace / "benchmarks" / "project_analyzer" / "projects" / "bot_with_handlers"

    result = run_transformation_flow(root=workspace, project_dir=project_dir, force=True)

    assert result["status"] == "promotion_ready"
    assert result["selected"]["capability"] == "bot.py:parse_command"
    quality_gate = json.loads(result["dry_run_promotion"]["quality_gate"])
    assert quality_gate["expected_output"] == {"result": ["sample", ""]}


def test_extraction_proposal_prefers_core_key_builder_over_middleware():
    candidates = [
        {"capability": "app/api/server.py:add_request_id_middleware", "why": "pure transform candidate"},
        {"capability": "app/core/cache.py:build_key", "why": "I/O or runtime boundary candidate"},
    ]
    python_structure = {
        "files": [
            {
                "functions": [
                    {
                        "path": "app/api/server.py",
                        "name": "add_request_id_middleware",
                        "args": [{"name": "request", "annotation": "Request"}],
                        "side_effects": [],
                        "loc": 12,
                        "is_async": True,
                    },
                    {
                        "path": "app/core/cache.py",
                        "name": "build_key",
                        "args": [{"name": "payload", "annotation": "dict"}],
                        "side_effects": ["memory_state"],
                        "loc": 6,
                    },
                ]
            }
        ]
    }

    selected = _select_candidate(candidates, python_structure)

    assert selected["capability"] == "app/core/cache.py:build_key"


def test_extraction_proposal_falls_back_when_first_candidate_has_unresolved_dependency(tmp_path):
    analyzer_outputs = {
        "project_map_report": {
            "summary": {"name": "sample"},
            "answers": {
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "capabilities_to_extract": [
                            {"capability": "pkg.py:first_candidate", "why": "pure transform candidate"},
                            {"capability": "pkg.py:second_candidate", "why": "pure transform candidate"},
                        ]
                    }
                }
            },
        },
        "extract_python_structure": {
            "files": [
                {
                    "functions": [
                        {
                            "path": "pkg.py",
                            "name": "first_candidate",
                            "args": [{"name": "value", "annotation": "str"}],
                            "returns": "bool",
                            "calls": ["external_lookup"],
                            "side_effects": [],
                            "source": "def first_candidate(value: str) -> bool:\n    return external_lookup(value)\n",
                            "loc": 2,
                        },
                        {
                            "path": "pkg.py",
                            "name": "second_candidate",
                            "args": [{"name": "value", "annotation": "str"}],
                            "returns": "str",
                            "calls": ["strip"],
                            "side_effects": [],
                            "source": "def second_candidate(value: str) -> str:\n    return value.strip()\n",
                            "loc": 2,
                        },
                    ]
                }
            ]
        },
    }

    proposal = build_extraction_proposal(
        project_dir=tmp_path / "sample",
        analyzer_outputs=analyzer_outputs,
    )

    assert proposal["status"] == "ok"
    assert proposal["selected"]["capability"] == "pkg.py:second_candidate"
    assert proposal["candidate_fallback"]["used"] is True
    assert proposal["skipped_candidates"][0]["selected"]["capability"] == "pkg.py:first_candidate"
    assert proposal["skipped_candidates"][0]["reason"] == "dependency_policy_blocked"


def test_contract_test_uses_python_literals_for_none():
    spec = {"quality_gate": {"sample_input": {"raw_bbox": "sample"}, "expected_output": {"result": None}}}

    source = _contract_test(spec)

    assert "null" not in source
    assert "{'result': None}" in source


def test_candidate_wrapper_imports_standard_modules_used_by_source():
    source = _main_py(
        "def is_ascii_encoding(encoding: str) -> bool:\n    return codecs.lookup(encoding).name == 'ascii'\n",
        "is_ascii_encoding",
        ["encoding"],
        "result",
    )

    assert "import codecs" in source


def test_transformation_flow_blocks_non_self_contained_candidate(tmp_path):
    workspace = _copy_workspace(tmp_path)
    project_dir = workspace / "external_dep_project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text(
        "def uses_external(value: str) -> bool:\n"
        "    return bool(external_lookup(value))\n",
        encoding="utf-8",
    )
    proposal = {
        "proposed_spec": {
            "id": "external_dep_project_uses_external",
            "input_contract": {"value": "string"},
            "output_contract": {"result": "boolean"},
            "quality_gate": {"sample_input": {"value": "sample"}, "expected_output": {"result": True}},
            "side_effects": {"filesystem": "none", "network": "none", "secrets": "none"},
            "source_extraction": {
                "project": "external_dep_project",
                "source": "main.py:uses_external",
                "line": 1,
                "loc": 2,
                "why": "test fixture",
            },
        },
        "selected": {"capability": "main.py:uses_external", "path": "main.py", "symbol": "uses_external"},
    }

    from runtime.transformation_flow import build_candidate_from_proposal

    try:
        build_candidate_from_proposal(workspace, project_dir, proposal, force=True)
    except NameError as exc:
        assert "external_lookup" in str(exc)
    else:
        raise AssertionError("expected unresolved external dependency to block candidate build")


def test_dependency_policy_allows_stdlib_imports():
    function = {"path": "compat.py", "name": "is_ascii", "calls": ["codecs.lookup"]}
    decision = evaluate_dependency_policy(function, {("compat.py", "is_ascii"): function})

    assert decision.status == "self_contained"
    assert decision.inline_imports == ["codecs"]


def test_dependency_policy_allows_safe_bare_method_calls():
    function = {"path": "main.py", "name": "normalize_text", "calls": ["join", "strip", "split"]}
    decision = evaluate_dependency_policy(function, {("main.py", "normalize_text"): function})

    assert decision.status == "self_contained"


def test_dependency_policy_blocks_local_domain_calls():
    function = {"path": "registry.py", "name": "is_supported", "calls": ["get_generation_family"]}
    helper = {"path": "registry.py", "name": "get_generation_family", "calls": []}
    decision = evaluate_dependency_policy(
        function,
        {("registry.py", "is_supported"): function, ("registry.py", "get_generation_family"): helper},
    )

    assert decision.status == "blocked"
    assert decision.unresolved_calls == ["get_generation_family"]


def test_dependency_policy_blocks_instance_bound_methods():
    function = {"path": "pipeline.py", "name": "materialize_result", "args": [{"name": "self"}], "calls": []}
    decision = evaluate_dependency_policy(function, {("pipeline.py", "materialize_result"): function})

    assert decision.status == "blocked"
    assert "object adapter policy" in decision.blockers[0]


def test_dependency_policy_blocks_subprocess_boundaries():
    function = {
        "path": "client.py",
        "name": "curl_fallback",
        "args": [{"name": "url"}],
        "calls": ["subprocess.run"],
        "side_effects": ["subprocess"],
    }
    decision = evaluate_dependency_policy(function, {("client.py", "curl_fallback"): function})

    assert decision.status == "blocked"
    assert any("subprocess" in blocker for blocker in decision.blockers)


def _copy_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    for name in ("runtime", "tools", "plugins", "pipelines", "registry", "generated", "benchmarks"):
        src = ROOT / name
        dst = workspace / name
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
    return workspace

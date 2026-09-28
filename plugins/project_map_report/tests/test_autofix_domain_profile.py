from plugins.project_map_report.src.main import run


def test_project_map_report_recognizes_llm_auto_repair_loop_and_demotes_attempt_noise():
    result = run(_autofix_like_payload())

    scope = result["answers"]["1_scope"]
    readiness = result["answers"]["6_runtime_extraction_readiness"]
    risk_codes = {risk["code"] for risk in result["risks"]}
    security_health = result["security_health"]
    active_core = {row["path"] for row in readiness["source_strata"]["active_core"]}
    context_only = {row["path"] for row in readiness["source_strata"]["context_only"]}
    packaged_copy = {row["path"] for row in readiness["source_strata"]["packaged_copy"]}
    capabilities = [row["capability"] for row in readiness["minimal_extraction_plan"]["capabilities_to_extract"]]

    assert scope["domain_profile"]["kind"] == "llm_auto_repair_loop"
    assert scope["main_task"].startswith("Run an LLM-assisted auto-repair loop")
    assert "secret_material_in_source" in risk_codes
    assert security_health["status"] == "attention_required"
    assert security_health["secret_hit_count"] == 1
    assert result["answers"]["0_security_health"] == security_health
    assert "## Security Health" in result["markdown"]
    assert "auto_dev_agent.py" in active_core
    assert "workspace/pipeline.py" in context_only
    assert "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py" in context_only
    assert "vx/AutoFix/auto_dev_agent.py" in packaged_copy
    assert capabilities[0].startswith("auto_dev_agent.py:")
    assert all("FixLog" not in item and "pipeline_backup" not in item for item in capabilities[:5])


def _autofix_like_payload() -> dict:
    return {
        "tree": {
            "root": "F:/ubuntu/AutoFix",
            "counts": {"files": 12, "directories": 6, "truncated": False},
            "files": [
                {"path": "main.py"},
                {"path": "auto_dev_agent.py"},
                {"path": "utils.py"},
                {"path": "workspace/pipeline.py"},
                {"path": "vx/AutoFix/auto_dev_agent.py"},
                {"path": "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py"},
                {"path": "vx/AutoFix/Template/pipeline_backup_20250803_023309.py"},
            ],
        },
        "stack": {
            "languages": [{"language": "Python"}],
            "frameworks": [],
            "entrypoints": ["main.py"],
            "large_artifacts": [],
            "dependency_files": [],
        },
        "files": {
            "files": [
                {"path": "config.json", "text": '{"llm": {"Deepseek": {"api_key": "sk-test", "base_url": "https://example.test/v1"}}}'},
                {
                    "path": "auto_dev_agent.py",
                    "text": "class AutoDevAgent:\n def docker_build(self): pass\n def docker_run(self): pass\n def send_to_model(self): pass\n def write_files(self): pass\n def copy_template(self): pass\n",
                },
                {"path": "utils.py", "text": "from openai import OpenAI\ndef run_prompt(messages): pass\n"},
            ]
        },
        "python_structure": {
            "imports": ["json", "openai", "os", "subprocess"],
            "routes": [],
            "files": [
                {
                    "path": "auto_dev_agent.py",
                    "functions": [
                        {
                            "path": "auto_dev_agent.py",
                            "name": "run",
                            "line": 100,
                            "loc": 40,
                            "calls": ["docker_build", "docker_run", "send_to_model", "write_files"],
                            "side_effects": ["filesystem", "subprocess"],
                            "error_profile": {},
                        },
                        {"path": "auto_dev_agent.py", "name": "send_to_model", "line": 70, "loc": 25, "calls": ["run_prompt", "json.loads"], "side_effects": ["network"], "error_profile": {}},
                        {"path": "auto_dev_agent.py", "name": "write_files", "line": 90, "loc": 20, "calls": ["Path.write_text"], "side_effects": ["filesystem"], "error_profile": {}},
                        {"path": "auto_dev_agent.py", "name": "docker_run", "line": 50, "loc": 20, "calls": ["subprocess.Popen"], "side_effects": ["subprocess"], "error_profile": {}},
                    ],
                },
                {"path": "workspace/pipeline.py", "functions": [{"path": "workspace/pipeline.py", "name": "process_batch", "line": 1, "loc": 80, "calls": [], "side_effects": [], "error_profile": {}}]},
                {"path": "vx/AutoFix/auto_dev_agent.py", "functions": [{"path": "vx/AutoFix/auto_dev_agent.py", "name": "run", "line": 1, "loc": 120, "calls": [], "side_effects": ["filesystem"], "error_profile": {}}]},
                {
                    "path": "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py",
                    "functions": [{"path": "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py", "name": "extract_reviews_from_page", "line": 1, "loc": 80, "calls": [], "side_effects": [], "error_profile": {}}],
                },
                {
                    "path": "vx/AutoFix/Template/pipeline_backup_20250803_023309.py",
                    "functions": [{"path": "vx/AutoFix/Template/pipeline_backup_20250803_023309.py", "name": "parse_review_block", "line": 1, "loc": 20, "calls": [], "side_effects": [], "error_profile": {}}],
                },
            ],
            "central_nodes": [
                {"path": "auto_dev_agent.py", "name": "run", "line": 100, "loc": 40, "call_count": 12, "side_effects": ["filesystem", "subprocess"]},
                {"path": "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py", "name": "extract_reviews_from_page", "line": 1, "loc": 80, "call_count": 30, "side_effects": []},
            ],
            "wide_functions": [
                {"path": "auto_dev_agent.py", "name": "run", "line": 100, "loc": 40, "call_count": 12, "side_effects": ["filesystem", "subprocess"]},
                {"path": "vx/AutoFix/FixLog/attempt_01/workspace/pipeline.py", "name": "extract_reviews_from_page", "line": 1, "loc": 80, "call_count": 30, "side_effects": []},
            ],
            "pure_transform_candidates": [
                {"path": "vx/AutoFix/Template/pipeline_backup_20250803_023309.py", "name": "parse_review_block", "line": 1, "loc": 20},
                {"path": "workspace/pipeline.py", "name": "process_batch", "line": 1, "loc": 80},
                {"path": "auto_dev_agent.py", "name": "extract_json_from_model_response", "line": 1, "loc": 12},
            ],
            "project_insights": {"test_surface": {}, "error_handling": {}},
            "contracts": {},
            "external_dependencies": {},
        },
        "runtime_commands": {"commands": []},
    }

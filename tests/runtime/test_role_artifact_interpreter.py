from __future__ import annotations

import json

from runtime.role_artifact_interpreter import load_role_artifact_pipeline, run_role_artifact_pipeline


def test_role_artifact_pipeline_is_loaded_from_external_config():
    pipeline = load_role_artifact_pipeline()

    assert pipeline["schema_version"] == "role_artifact_pipeline.v1"
    assert pipeline["steps"]
    assert all("builder" in step for step in pipeline["steps"])


def test_interpreter_runs_custom_pipeline_without_code_change(tmp_path):
    module_path = tmp_path / "custom_builders.py"
    module_path.write_text(
        "def build_sql_artifact(**kwargs):\n"
        "    return {'artifact_type': 'SqlArchitectureDecision', 'role': 'sql_architect', 'status': 'ok', 'goal': kwargs['goal']}\n",
        encoding="utf-8",
    )
    pipeline = {
        "schema_version": "role_artifact_pipeline.v1",
        "steps": [
            {
                "step_id": "sql_architecture",
                "role_id": "sql_architect",
                "builder": "custom_builders:build_sql_artifact",
                "output_key": "sql_architecture",
                "bindings": {"goal": "$goal"},
            }
        ],
    }

    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        artifacts = run_role_artifact_pipeline(
            goal="Analyze SQL schema",
            project_report={},
            pipeline=pipeline,
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert artifacts["sql_architecture"]["role"] == "sql_architect"
    assert artifacts["sql_architecture"]["goal"] == "Analyze SQL schema"


def test_pipeline_config_can_be_round_tripped(tmp_path):
    path = tmp_path / "pipeline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "role_artifact_pipeline.v1",
                "steps": [
                    {
                        "step_id": "noop",
                        "role_id": "noop",
                        "builder": "module:function",
                        "output_key": "noop",
                        "bindings": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_role_artifact_pipeline(str(path))["steps"][0]["role_id"] == "noop"

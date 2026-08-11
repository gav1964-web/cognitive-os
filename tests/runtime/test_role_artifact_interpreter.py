from __future__ import annotations

import json

from runtime.role_artifact_interpreter import load_role_artifact_pipeline, run_role_artifact_pipeline
from runtime.role_directory import load_role_directory


def test_role_artifact_pipeline_is_loaded_from_external_config():
    pipeline = load_role_artifact_pipeline()

    assert pipeline["schema_version"] == "role_artifact_pipeline.v1"
    assert pipeline["steps"]
    assert all("builder" in step for step in pipeline["steps"])


def test_interpreter_runs_custom_builder_without_core_change(tmp_path):
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


def test_interpreter_runs_new_role_from_config_only(tmp_path):
    directory_path = tmp_path / "role_directory.json"
    directory_path.write_text(
        json.dumps(
            {
                "schema_version": "role_directory.v2",
                "status": "active",
                "roles": {
                    "sql_architect": {
                        "label": "SQL Architect",
                        "description": "Produces a bounded SQL architecture decision.",
                        "capabilities": ["describe_sql_boundary"],
                        "consumes": ["Goal"],
                        "produces": ["SqlArchitectureDecision"],
                        "contract": {
                            "inputs": [{"name": "goal", "artifact_type": "Goal", "required": True}],
                            "outputs": [
                                {
                                    "name": "sql_architecture",
                                    "artifact_type": "SqlArchitectureDecision",
                                    "required": True,
                                }
                            ],
                        },
                        "gates": [],
                        "fallback_policy": {},
                        "llm_policy": {"allowed": False},
                        "kb_policy": {"read": True, "auto_promote": False},
                        "policy": {"source_mutation": "forbidden"},
                        "stop_conditions": [],
                        "quality_criteria": [],
                        "artifact_builder": {
                            "builder_id": "sql_architecture_declarative_v1",
                            "callable": "runtime.role_artifact_builder:build_declarative_artifact",
                            "artifact_type": "SqlArchitectureDecision",
                            "kwargs": {
                                "artifact_type": "SqlArchitectureDecision",
                                "include_inputs": ["goal"],
                                "static_fields": {"decision": "preserve transaction boundary"},
                            },
                        },
                    }
                },
                "pipeline": [
                    {
                        "step_id": "sql_architecture",
                        "role_id": "sql_architect",
                        "phase": "build",
                        "output_key": "sql_architecture",
                        "bindings": {"goal": "$goal"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    directory = load_role_directory(str(directory_path))

    artifacts = run_role_artifact_pipeline(
        goal="Analyze SQL schema",
        project_report={},
        directory=directory,
    )

    assert artifacts["sql_architecture"] == {
        "artifact_type": "SqlArchitectureDecision",
        "role": "sql_architect",
        "status": "ok",
        "decision": "preserve transaction boundary",
        "goal": "Analyze SQL schema",
    }


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

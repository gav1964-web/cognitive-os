import json
from pathlib import Path

from runtime.exception_pickle_failed_probe_analyzer import (
    run_exception_pickle_failed_probe_analyzer,
)


def test_failed_probe_analyzer_marks_exception_alias_probe_stale_when_sample_now_supported(
    tmp_path: Path,
):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "discord",
            "project_root": "discord",
            "path": "errors.py",
            "class_name": "CommandInvokeError",
            "required_constructor_parameters": ["command", "e"],
        }],
    )
    project = tmp_path / "discord"
    project.mkdir()
    (project / "errors.py").write_text(
        "class CommandInvokeError(Exception):\n"
        "    def __init__(self, command, e):\n"
        "        self.original = e\n"
        "        self.command = command\n"
        "        super().__init__(f'Command {command.name!r}: {e}')\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_precheck",
            "blocker_kind": "semantic_sample_shape_unsupported",
            "failed_checks": ["semantic_samples_supported"],
            "candidate": {
                "project": "discord",
                "target": "errors.py:CommandInvokeError.__init__",
            },
        }],
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
    )

    assert result["failed_probe_case_count"] == 1
    assert result["failure_subtype_summary"] == {"stale_probe_now_sample_supported": 1}
    assert result["recommended_next_repair_lane"]["repair_lane"] == (
        "active_application_reprobe"
    )
    assert result["cases"][0]["unsupported_sample_inputs"] == []


def test_failed_probe_analyzer_classifies_self_referential_capture_gap(tmp_path: Path):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "graphql",
            "project_root": "graphql",
            "path": "client.py",
            "class_name": "GraphqlWsResponseError",
            "required_constructor_parameters": ["response"],
        }],
    )
    project = tmp_path / "graphql"
    project.mkdir()
    (project / "client.py").write_text(
        "class GraphqlWsResponseError(Exception):\n"
        "    def __init__(self, response, message=None):\n"
        "        super().__init__(self)\n"
        "        self.message = message\n"
        "        self.response = response\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_semantic_replay",
            "blocker_kind": "semantic_replay_behavior_mismatch",
            "failed_checks": ["project_native_semantic_replay"],
            "candidate": {
                "project": "graphql",
                "target": "client.py:GraphqlWsResponseError.__init__",
            },
            "project_native_semantic_replay": {
                "status": "failed",
                "stderr": "RecursionError: maximum recursion depth exceeded",
            },
        }],
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
    )

    assert result["failure_subtype_summary"] == {
        "self_referential_super_init_object_state_replay_gap": 1,
    }
    assert result["recommended_next_repair_lane"]["repair_lane"] == (
        "semantic_replay_capture_repair"
    )
    assert "self_referential_super_init" in result["cases"][0]["source_facts"]["fact_tags"]


def test_failed_probe_analyzer_marks_old_precheck_as_reprobe_when_sample_now_supported(
    tmp_path: Path,
):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "alembic",
            "project_root": "alembic",
            "path": "revision.py",
            "class_name": "RangeNotAncestorError",
            "required_constructor_parameters": ["lower", "upper"],
        }],
    )
    project = tmp_path / "alembic"
    project.mkdir()
    (project / "revision.py").write_text(
        "class RangeNotAncestorError(Exception):\n"
        "    def __init__(self, lower, upper):\n"
        "        self.lower = lower\n"
        "        self.upper = upper\n"
        "        super().__init__('Revision %s is not an ancestor of revision %s' % (lower or 'base', upper or 'base'))\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_precheck",
            "blocker_kind": "semantic_sample_shape_unsupported",
            "failed_checks": ["semantic_samples_supported"],
            "candidate": {
                "project": "alembic",
                "target": "revision.py:RangeNotAncestorError.__init__",
            },
        }],
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
    )

    assert result["failure_subtype_summary"] == {
        "stale_probe_now_sample_supported": 1,
    }
    assert result["recommended_next_repair_lane"]["repair_lane"] == (
        "active_application_reprobe"
    )
    assert result["cases"][0]["unsupported_sample_inputs"] == []


def test_failed_probe_analyzer_excludes_targets_already_applied_in_ledger(tmp_path: Path):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "pact",
            "project_root": "pact",
            "path": "error.py",
            "class_name": "InteractionVerificationError",
            "required_constructor_parameters": ["description", "error"],
        }],
    )
    project = tmp_path / "pact"
    project.mkdir()
    (project / "error.py").write_text(
        "class InteractionVerificationError(Exception):\n"
        "    def __init__(self, description, error):\n"
        "        self.description = description\n"
        "        self.error = error\n"
        "        super().__init__(f\"Error verifying interaction '{description}': {error}\")\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_precheck",
            "blocker_kind": "semantic_sample_shape_unsupported",
            "failed_checks": ["semantic_samples_supported"],
            "candidate": {
                "project": "pact",
                "target": "error.py:InteractionVerificationError.__init__",
            },
        }],
    )
    application_ledger = tmp_path / "application-ledger.json"
    application_ledger.write_text(
        json.dumps({
            "cases": [{
                "project": "pact",
                "target": "error.py:InteractionVerificationError.__init__",
                "status": "applied_active_kb",
            }],
        }),
        encoding="utf-8",
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
        application_ledger_path=application_ledger,
    )

    assert result["status"] == "empty"
    assert result["failed_probe_case_count"] == 0
    assert result["repair_lane_summary"] == {}


def test_failed_probe_analyzer_uses_latest_report_only_attempt_per_target(tmp_path: Path):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "alembic",
            "project_root": "alembic",
            "path": "revision.py",
            "class_name": "RangeNotAncestorError",
            "required_constructor_parameters": ["lower", "upper"],
        }],
    )
    project = tmp_path / "alembic"
    project.mkdir()
    (project / "revision.py").write_text(
        "class RangeNotAncestorError(Exception):\n"
        "    def __init__(self, lower, upper):\n"
        "        self.lower = lower\n"
        "        self.upper = upper\n"
        "        super().__init__('Revision %s is not an ancestor of revision %s' % (lower or 'base', upper or 'base'))\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_precheck",
            "blocker_kind": "semantic_sample_shape_unsupported",
            "failed_checks": ["semantic_samples_supported"],
            "candidate": {
                "project": "alembic",
                "target": "revision.py:RangeNotAncestorError.__init__",
            },
        }],
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_semantic_replay",
            "blocker_kind": "semantic_replay_behavior_mismatch",
            "failed_checks": ["project_native_semantic_replay"],
            "candidate": {
                "project": "alembic",
                "target": "revision.py:RangeNotAncestorError.__init__",
            },
            "project_native_semantic_replay": {
                "status": "failed",
                "stderr": "behavior differs",
            },
        }],
        name="exception_pickle_active_application_20260903T000001000000Z.json",
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
    )

    assert result["failure_subtype_summary"] == {
        "semantic_behavior_mismatch_under_direct_file_probe": 1,
    }
    assert result["recommended_next_repair_lane"]["repair_lane"] == (
        "semantic_behavior_contrast_research"
    )


def test_failed_probe_analyzer_classifies_base_constructor_passthrough_contract_gap(
    tmp_path: Path,
):
    _write_audit(
        tmp_path,
        [{
            "canonical_project": "netbox",
            "project_root": "netbox",
            "path": "exceptions.py",
            "class_name": "SearchError",
            "required_constructor_parameters": ["message"],
        }],
    )
    project = tmp_path / "netbox"
    project.mkdir()
    (project / "exceptions.py").write_text(
        "class IngestionIssue(Exception):\n"
        "    def __init__(self, model_string, data):\n"
        "        self.model_string = model_string\n"
        "        self.data = data\n"
        "\n"
        "class SearchError(IngestionIssue, LookupError):\n"
        "    def __init__(self, message, *args, **kwargs):\n"
        "        super().__init__(*args, **kwargs)\n"
        "        self.message = message\n",
        encoding="utf-8",
    )
    _write_probe(
        tmp_path,
        [{
            "status": "blocked_semantic_replay",
            "blocker_kind": "semantic_replay_behavior_mismatch",
            "failed_checks": ["project_native_semantic_replay"],
            "candidate": {
                "project": "netbox",
                "target": "exceptions.py:SearchError.__init__",
            },
            "project_native_semantic_replay": {
                "status": "failed",
                "stderr": (
                    "TypeError: IngestionIssue.__init__() missing 2 required "
                    "positional arguments: 'model_string' and 'data'"
                ),
            },
        }],
    )

    result = run_exception_pickle_failed_probe_analyzer(
        root=tmp_path,
        audit_path=tmp_path / "audit.json",
    )

    assert result["failure_subtype_summary"] == {
        "base_constructor_passthrough_contract_gap": 1,
    }
    assert result["recommended_next_repair_lane"]["repair_lane"] == (
        "constructor_state_contract_research"
    )
    assert "base_constructor_passthrough" in result["cases"][0]["source_facts"]["fact_tags"]


def _write_audit(tmp_path: Path, candidates: list[dict]) -> None:
    (tmp_path / "audit.json").write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleCandidateAudit",
            "candidates": candidates,
        }),
        encoding="utf-8",
    )


def _write_probe(
    tmp_path: Path,
    attempts: list[dict],
    *,
    name: str = "exception_pickle_active_application_20260903T000000000000Z.json",
) -> None:
    out = tmp_path / "artifacts" / "project_development"
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(
        json.dumps({
            "artifact_type": "ExceptionPickleActiveApplicationTrial",
            "generated_at": name.removeprefix("exception_pickle_active_application_").removesuffix(".json"),
            "update_application_ledger": False,
            "attempts": attempts,
        }),
        encoding="utf-8",
    )

from pathlib import Path

from runtime._parts.role_foundation_field_trial_scope import _primary_language_scope
from runtime._parts import architecture_decision_builder_part3 as architecture_builder_part3
import runtime.architecture_decision_builder as architecture_builder
from runtime.module_script_boundary import enrich_module_script_readiness
from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def _candidate(snippet: str, names: list[str]) -> dict:
    return {
        "signature": {"args": [{"name": name, "annotation": ""} for name in names], "returns": ""},
        "snippet": snippet,
    }


def test_percent_formatting_proves_scalar_input_usage():
    evidence = infer_source_contract(
        _candidate("def check(value, label):\n    raise ValueError('%s: %s' % (label, value))", ["value", "label"])
    )

    assert evidence["argument_usage_types"] == {"label": "ScalarLike", "value": "ScalarLike"}


def test_alloc_delegation_has_concrete_output_shape():
    evidence = infer_source_contract(
        _candidate("def alloc(self, *args, **kwargs):\n    return self.obj_space().alloc(*args, **kwargs)", [])
    )

    assert evidence["inferred_output_type"] == "AllocatedObjectLike"


def test_source_proven_pure_domain_helper_is_not_penalized():
    target = "package/anonymization/helpers.py:strip_tag"
    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        selection_reason="pure transform",
        structural_evidence={"source_body_complete": True, "argument_count": 1, "state_mutation": False},
        input_contract={"label": "str"},
        output_contract={"result": "str"},
        side_effect_contract={"declared": []},
    )

    assert report["score"] >= 97
    assert not any("support/utility target" in reason for reason in report["reasons"])


def test_infrastructure_repository_with_incidental_integration_scripts_is_out_of_scope(tmp_path: Path):
    integrations = tmp_path / "integrations"
    integrations.mkdir()
    for name in ("publish.py", "report.py"):
        (integrations / name).write_text("print('integration')\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")
    terraform = tmp_path / "terraform"
    terraform.mkdir()
    (terraform / "main.tf").write_text("resource \"null_resource\" \"demo\" {}\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_legacy_active_core_script_becomes_module_boundary(tmp_path: Path):
    source = tmp_path / "legacy_train.py"
    source.write_text("print 'training'\n", encoding="utf-8")
    report = {
        "summary": {"root": tmp_path.as_posix(), "entrypoints": []},
        "source_health": {
            "status": "noisy",
            "project_shape": "single_project",
            "parser_incompatibility_count": 1,
            "syntax_error_count": 0,
            "artifact_noise_signal_count": 0,
            "inaccessible_count": 0,
        },
        "answers": {
            "2_execution": {"entrypoints": []},
            "6_runtime_extraction_readiness": {
                "source_strata": {"active_core": [{"path": source.name}]},
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [],
                    "blocked_by": ["no_safe_python_candidate"],
                },
            },
        },
    }

    result = enrich_module_script_readiness(report)
    plan = result["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"]

    assert plan["capabilities_to_extract"][0]["capability"] == source.name
    assert plan["blocked_by"] == []
    assert len(result["answers"]["6_runtime_extraction_readiness"]["data_lifecycle"]) == 3


def test_module_script_candidate_binds_architect_first_slice():
    first_slice = {"name": "compute_slice", "targets": [], "steps": ["run compute"]}
    plan = {"capabilities_to_extract": [{"capability": "scripts/train.py"}]}

    result = architecture_builder._first_slice_with_source_targets(first_slice, [], plan=plan)

    assert result["targets"] == ["scripts/train.py"]


def test_short_architecture_risk_is_expanded_with_target_context():
    result = architecture_builder._risk_record(
        source="analysis_task",
        severity="high",
        description="Review os decision",
        mitigation="record an explicit decision",
        category="REVIEW_HUMAN_DECISION",
        target="os",
    )

    assert len(result["description"]) >= 32
    assert "target `os`" in result["description"]


def test_active_core_files_are_kept_as_architecture_context(monkeypatch):
    monkeypatch.setattr(
        architecture_builder_part3,
        "_provider_parser_sources",
        lambda _root: (_ for _ in ()).throw(AssertionError("rootless scan forbidden")),
    )
    report = {
        "answers": {
            "3_capabilities": {},
            "6_runtime_extraction_readiness": {
                "source_strata": {"active_core": [{"path": "legacy/train.py"}]},
            },
        },
    }

    assert "legacy/train.py" in architecture_builder._important_runtime_sources(report)

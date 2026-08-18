from __future__ import annotations

import json
from pathlib import Path

from runtime.contract_transform_contract_profiles import (
    contract_profile_hint,
    load_contract_transform_contract_profiles,
    profile_positive_case,
)
from runtime.implementation_plan_builder import build_implementation_plan
from runtime.programmer_executor import run_programmer_executor
from runtime.role_spec_writer_ranking import name_and_contract_score
from runtime.spec_writer_ranking_kb import load_spec_writer_ranking_kb
from runtime.technical_spec_builder import build_technical_spec
from runtime.test_plan_builder import build_test_plan
from runtime.technical_spec_contract_enrichment import enrich_signature_contract


def _implementation_plan(target: str, *, oracle_authority: str = "") -> dict[str, object]:
    return {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target},
        "patch_scope": [target],
        "writable_scope": [target],
        "expected_files": [target.split(":", 1)[0]],
        "verification_commands": ["python -m compileall ."],
        "contract_binding": {
            "binding_status": "bound_to_extraction_contract",
            "input_contract": {"name": "str"},
            "output_contract": {"result": "str"},
            "contract_profile": {
                "id": "normalize_string",
                "operator_id": "strip_lower",
                "oracle_authority": oracle_authority,
            },
        },
    }


def test_contract_transform_profiles_load_and_select_normalize_case():
    catalog = load_contract_transform_contract_profiles()
    case = profile_positive_case(
        target="main.py:normalize_name",
        input_contract={"name": "str"},
        output_contract={"result": "str"},
        catalog=catalog,
    )

    assert case
    assert case["given"] == {"name": " Sample "}
    assert case["expect"] == {"return_value": "sample"}
    assert case["operator_id"] == "strip_lower"


def test_bound_profile_takes_precedence_over_broader_name_match():
    case = profile_positive_case(
        target="main.py:normalize_option_name",
        input_contract={"name": "str"},
        output_contract={"result": "str"},
        profile_id="normalized_option_name",
    )

    assert case
    assert case["operator_id"] == "lower_replace_dash"


def test_contract_profile_hint_enriches_inferred_signature_contract():
    hint = contract_profile_hint(
        target="main.py:normalize_name",
        input_contract={"name": "InferredName"},
        output_contract={"result": "InferredOutput"},
    )

    assert hint
    assert hint["input_contract"] == {"name": "str"}
    assert hint["output_contract"] == {"result": "str"}
    assert hint["contract_profile"]["operator_id"] == "strip_lower"


def test_source_observed_operator_authorizes_literal_oracle():
    enriched = enrich_signature_contract(
        target="main.py:normalize_name",
        input_contract={"name": "str"},
        output_contract={"result": "str"},
        source_snippet="def normalize_name(name):\n    return name.strip().lower()",
    )

    assert enriched["contract_profile"]["oracle_authority"] == "source_observed_operator"
    plan = _implementation_plan("main.py:normalize_name")
    plan["contract_binding"]["contract_profile"] = enriched["contract_profile"]
    test_plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "normalizes"}]},
        implementation_plan=plan,
    )
    assert test_plan["executable_acceptance"]["obligations"][0]["expect"] == {"return_value": "sample"}


def test_nonmatching_normalize_implementation_keeps_name_hint_non_authoritative():
    enriched = enrich_signature_contract(
        target="auth.py:_normalize_api_key",
        input_contract={"api_key": "str"},
        output_contract={"result": "str"},
        source_snippet=(
            "def _normalize_api_key(api_key):\n"
            "    return api_key if '@' in api_key else f'{api_key}@AMER.OAUTHAP'"
        ),
    )

    assert enriched["contract_profile"]["oracle_authority"] == "name_hint_only"


def test_spec_writer_ranking_treats_name_profile_as_weak_hint():
    score, reasons = name_and_contract_score(
        "main.py:normalize_name",
        {"args": [{"name": "name", "annotation": ""}], "returns": ""},
        [],
    )

    assert score
    assert load_spec_writer_ranking_kb()["adjustments"]["profile.executable"]["score"] == 3
    assert any("non-authoritative contract profile normalize_string" in reason for reason in reasons)


def test_test_plan_builder_does_not_treat_name_hint_as_literal_oracle():
    plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "name is normalized"}]},
        implementation_plan=_implementation_plan("main.py:normalize_name"),
    )

    obligation = plan["executable_acceptance"]["obligations"][0]
    assert obligation["given"] == {"name": "value"}
    assert obligation["expect"] == {"result": "str"}
    assert "contract_profile" not in obligation
    assert obligation["invocation_pattern"]["id"] == "keyword_scalar_contract"


def test_explicit_architect_profile_authorizes_literal_oracle():
    plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "name is normalized"}]},
        implementation_plan=_implementation_plan(
            "main.py:normalize_name", oracle_authority="explicit_architect_request"
        ),
    )

    obligation = plan["executable_acceptance"]["obligations"][0]
    assert obligation["given"] == {"name": " Sample "}
    assert obligation["expect"] == {"return_value": "sample"}


def test_role_builders_carry_transform_profile_into_executable_test_plan():
    spec = build_technical_spec(architecture_decision=_adr_for_normalize_name())
    plan = build_implementation_plan(technical_spec=spec)
    test_plan = build_test_plan(technical_spec=spec, implementation_plan=plan)

    assert spec["extraction_contract"]["contract_profile"]["operator_id"] == "strip_lower"
    assert spec["extraction_contract"]["input_contract"] == {"name": "str"}
    assert spec["extraction_contract"]["output_contract"] == {"result": "str"}
    assert plan["contract_binding"]["contract_profile"]["operator_id"] == "strip_lower"
    assert spec["extraction_contract"]["contract_profile"]["oracle_authority"] == "name_hint_only"
    obligation = test_plan["executable_acceptance"]["obligations"][0]
    assert obligation["given"] == {"name": "value"}
    assert obligation["expect"] == {"result": "str"}


def test_executor_does_not_invent_transform_from_name_only(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize_name(name):\n    return name\n", encoding="utf-8")
    spec = build_technical_spec(architecture_decision=_adr_for_normalize_name())
    implementation_plan = build_implementation_plan(technical_spec=spec)
    test_plan = build_test_plan(technical_spec=spec, implementation_plan=implementation_plan)

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert "return name.strip().lower()" not in source


def test_executor_uses_profiled_test_plan_to_synthesize_transform(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize_name(name):\n    return name\n", encoding="utf-8")
    implementation_plan = _implementation_plan(
        "main.py:normalize_name", oracle_authority="explicit_architect_request"
    )
    test_plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "name is normalized"}]},
        implementation_plan=implementation_plan,
    )

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "contract_transform_identity_return_synthesized"
    assert patch["patches"][0]["transform"] == "strip_lower"
    assert "return name.strip().lower()" in source


def _adr_for_normalize_name() -> dict[str, object]:
    target = "main.py:normalize_name"
    return {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Implement deterministic transform contract",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare normalize_name for implementation."],
            "files_or_symbols": [target],
        },
        "traceability": [{"source": target, "requirement": "Capability candidate requires TechnicalSpec."}],
        "source_context": {
            target: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "name", "annotation": ""}], "returns": ""},
                "snippet": {"text": "def normalize_name(name):\n    return name"},
            }
        },
    }

from runtime.framework_plugin_role_semantics import (
    evaluate_framework_plugin_role_semantics,
)


def _project() -> dict:
    return {
        "summary": {
            "entrypoints": ["pyproject.toml:[plugin:pytest11]:demo=package.pytest_plugin"]
        },
        "answers": {
            "1_scope": {
                "main_task": "Provide a pytest plugin for collecting domain test cases.",
                "supported_scenarios": ["Load pytest hooks", "Collect plugin test cases"],
                "domain_profile": {"kind": "pytest_plugin"},
            }
        },
    }


def _adr() -> dict:
    return {
        "decision_summary": "Keep pytest hook registration isolated from case collection.",
        "architecture_options": [{"id": "pytest_hook_boundary"}],
        "first_slice_contract": {"targets": ["package/pytest_plugin.py:pytest_configure"]},
    }


def _spec() -> dict:
    target = "package/pytest_plugin.py:pytest_configure"
    return {
        "extraction_contract": {"candidate": target},
        "requirements": [{"statement": f"Preserve `{target}` registration.", "target": target}],
        "acceptance_criteria": [{
            "criterion": "A duplicate plugin registration is rejected.",
            "verification": "pytest tests/test_pytest_plugin.py::test_duplicate_registration",
            "source": target,
        }],
    }


def _classification() -> dict:
    return {
        "effective_project_identity": "framework_plugin_build",
        "project_archetype": "pytest_plugin",
        "project_archetype_scope": "domain",
    }


def test_framework_semantics_rejects_generic_unrelated_multitarget_chain(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.framework_plugin_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value: {"role_scores": {
            "project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0
        }},
    )
    spec = _spec()
    spec["extraction_contract"]["candidate"] = "package/queue.py:wait_for_queue"
    spec["requirements"] = [{
        "statement": "Keep writable scope limited to `package/queue.py:wait_for_queue`.",
        "target": "package/database.py:connect",
    }]
    spec["acceptance_criteria"] = [
        {"criterion": f"Target `{name}` works.", "verification": "pytest or explicit review checklist", "source": name}
        for name in ("package/queue.py:wait_for_queue", "package/database.py:connect")
    ]
    adr = _adr()
    adr["decision_summary"] = "Treat C:/project as a candidate for bounded capability extraction: 12 candidates."
    adr["architecture_options"] = [{"id": "minimal_safe_extraction"}]

    result = evaluate_framework_plugin_role_semantics(
        project_report=_project(), architecture_decision=adr, technical_spec=spec,
        classification=_classification(), goal="GitHub full-chain probe for demo",
        executor={"patch_synthesis_status": "verification_only", "source_code_changes": False},
    )

    assert result["status"] == "needs_work"
    assert result["role_scores"]["architect"] < 9.7
    assert result["role_scores"]["spec_writer"] < 9.7
    assert result["development_change_evaluated"] is False


def test_framework_semantics_accepts_specific_consistent_chain(monkeypatch) -> None:
    monkeypatch.setattr(
        "runtime.framework_plugin_role_semantics.evaluate_foundation_semantic_quality",
        lambda _value: {"role_scores": {
            "project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0
        }},
    )
    result = evaluate_framework_plugin_role_semantics(
        project_report=_project(), architecture_decision=_adr(), technical_spec=_spec(),
        classification=_classification(), goal="Fix duplicate pytest plugin registration",
        executor={"patch_synthesis_status": "prepared", "patch_count": 1},
    )

    assert result["status"] == "passed"
    assert min(result["role_scores"].values()) >= 9.7
    assert result["development_change_evaluated"] is True

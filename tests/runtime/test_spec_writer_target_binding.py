from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill


def test_spec_writer_rejects_nested_function_and_selects_standalone_alternative():
    spec = _run_spec_writer(
        ["workflow.py:inner", "workflow.py:normalize"],
        {
            "workflow.py:inner": _context("inner", target_binding="nested_function"),
            "workflow.py:normalize": _context("normalize"),
        },
    )

    contract = spec["extraction_contract"]
    assert contract["candidate"] == "workflow.py:normalize"
    assert contract["binding_rejections"] == [{
        "source": "workflow.py:inner",
        "target_binding": "nested_function",
        "reason": "nested function depends on enclosing closure state and is not a standalone extraction target",
        "reason_code": "nested_function_requires_closure",
    }]


def test_spec_writer_blocks_when_only_candidate_requires_closure():
    spec = _run_spec_writer(
        ["workflow.py:inner"],
        {"workflow.py:inner": _context("inner", target_binding="nested_function")},
    )

    contract = spec["extraction_contract"]
    assert contract["status"] == "blocked_no_safe_candidate"
    assert contract["candidate"] is None
    assert contract["blocked_by"] == ["nested_function_requires_closure"]


def _context(symbol: str, *, target_binding: str = "") -> dict:
    row = {
        "kind": "pure_transform",
        "signature": {"args": [{"name": "value", "annotation": "str"}], "returns": "str"},
        "snippet": {"text": f"def {symbol}(value): return value.strip()"},
    }
    if target_binding:
        row["target_binding"] = target_binding
    return row


def _run_spec_writer(sources: list[str], source_context: dict) -> dict:
    return run_role_skill(
        producer_for_artifact_type("TechnicalSpec"),
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "role": "architect",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {
                "scope": ["Prepare one implementable capability extraction spec."],
                "files_or_symbols": sources,
            },
            "traceability": [
                {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
                for source in sources
            ],
            "source_context": source_context,
        }
    )

from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill


def test_spec_writer_considers_targets_beyond_legacy_eight_item_window():
    weak = [f"pkg/accessors.py:get_value_{index}" for index in range(10)]
    selected = "pkg/domain.py:parse_payload"
    targets = [*weak, selected]
    adr = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": "architect",
        "goal": "Use the configured first-slice candidate window",
        "chosen_option": {"id": "minimal_safe_extraction"},
        "spec_writer_brief": {
            "scope": ["Prepare one implementable capability extraction spec."],
            "files_or_symbols": targets,
            "first_slice": {"targets": targets, "steps": ["Specify the bounded capability."]},
        },
        "traceability": [],
        "source_context": {
            **{
                source: {
                    "kind": "unknown",
                    "signature": {"args": [], "returns": "str"},
                    "snippet": {"text": "def get_value(): return 'value'"},
                }
                for source in weak
            },
            selected: {
                "kind": "pure_transform",
                "signature": {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
                "snippet": {"text": "def parse_payload(payload): return ParsedPayload(payload)"},
            },
        },
    }

    spec = run_role_skill(
        producer_for_artifact_type("TechnicalSpec"), architecture_decision=adr
    )

    assert selected in spec["work_plan_contract"]["targets"]
    assert spec["extraction_contract"]["candidate"] == selected

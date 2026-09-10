from runtime.interpreter_authority import verify_interpreter_decision
from runtime.role_recovery_contract import build_role_recovery_contract


def test_role_return_is_bounded_and_never_authorizes_retry():
    contract = build_role_recovery_contract(
        producer="tester",
        return_to="implementer",
        outcome="needs_rework",
        reason_code="acceptance_failed",
        target="src/parser.py:parse",
        scope=["src/parser.py"],
        original_target="src/parser.py:parse",
        original_scope=["src/parser.py", "tests/test_parser.py"],
    )

    assert contract["status"] == "return_ready"
    assert contract["execution_authorized"] is False
    assert contract["automatic_retry"] is False
    assert contract["interpreter_decision_trace"]["next_stage"] == "implementation"
    assert verify_interpreter_decision(contract["interpreter_decision_trace"])["status"] == "verified"


def test_role_return_blocks_target_reselection_and_scope_expansion():
    contract = build_role_recovery_contract(
        producer="reviewer",
        return_to="architect",
        outcome="needs_rework",
        reason_code="wrong_target",
        target="src/easy.py:rewrite",
        scope=["src/parser.py", "src/easy.py"],
        original_target="src/parser.py:parse",
        original_scope=["src/parser.py"],
        previous_returns=2,
    )

    assert contract["status"] == "controlled_stop"
    assert set(contract["failed_checks"]) >= {
        "target_preserved", "scope_not_expanded", "return_budget_available"
    }

from runtime.requested_contract_profile import bind_requested_contract_profile


def _adr(operator: str = "slash_to_dot") -> dict:
    return {
        "goal": f"Implement verified {operator} transform",
        "spec_writer_brief": {
            "files_or_symbols": ["main.py:path_to_dots"],
            "requested_contract_profile": {
                "id": "slash_to_dot",
                "operator_id": operator,
                "evidence": "pkg/path.py:path_to_dots",
            },
        },
        "source_context": {
            "main.py:path_to_dots": {
                "signature": {"args": [{"name": "path"}]},
                "snippet": {"text": "def path_to_dots(path):\n    return path"},
            }
        },
    }


def test_requested_profile_rebinds_explicit_local_change() -> None:
    bound = bind_requested_contract_profile(
        _adr(),
        {"status": "blocked_no_safe_candidate", "ranked_candidates": [{"source": "main.py:path_to_dots", "score": 70}]},
    )

    assert bound["candidate"] == "main.py:path_to_dots"
    assert bound["contract_profile"]["operator_id"] == "slash_to_dot"
    assert bound["input_contract"] == {"path": "str"}
    assert bound["requested_profile_binding"]["status"] == "verified"


def test_requested_profile_rejects_goal_without_exact_operator_authority() -> None:
    adr = _adr()
    adr["goal"] = "Analyze path helper"
    original = {"status": "blocked_no_safe_candidate"}

    assert bind_requested_contract_profile(adr, original) == original

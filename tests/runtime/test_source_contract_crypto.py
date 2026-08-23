from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report


def test_unpadding_call_is_inferred_as_bytes():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "value", "annotation": ""}], "returns": ""},
            "snippet": "def decrypt(value):\n    return Crypto.__unpad(cipher.decrypt(value))",
        }
    )

    assert evidence["inferred_output_type"] == "bytes"


def test_password_verification_proves_string_inputs_and_boolean_output():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "plain", "annotation": ""}, {"name": "hashed", "annotation": ""}]},
            "snippet": "def verify_password(plain, hashed):\n    return pwd_context.verify(plain, hashed)",
        }
    )

    assert evidence["argument_usage_types"] == {"plain": "str", "hashed": "str"}
    assert evidence["inferred_output_type"] == "bool"


def test_digest_chain_proves_structural_contract_family():
    target = "app/security.py:hash_token"
    evidence = infer_source_contract(
        {
            "signature": {
                "args": [{"name": "raw", "annotation": "str"}],
                "returns": "str",
            },
            "snippet": (
                "def hash_token(raw: str) -> str:\n"
                "    return hashlib.sha256(raw.encode()).hexdigest()"
            ),
        }
    )

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        structural_evidence=evidence,
        input_contract={"raw": "str"},
        output_contract={"result": "str"},
        side_effect_contract={"declared": []},
    )

    assert "hexdigest" in evidence["called_operations"]
    assert report["contract_archetype_ids"] == ["cryptographic_digest_transform"]
    assert report["score"] >= 97

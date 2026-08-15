from runtime.configured_role_pipeline import producer_for_artifact_type
from runtime.role_skills import run_role_skill


def test_spec_writer_prefers_environment_ready_candidate():
    sources = ["pkg/optional.py:run", "pkg/core.py:normalize"]
    context = {
        "pkg/optional.py:run": _context("run", ["missing_runtime_sdk"]),
        "pkg/core.py:normalize": _context("normalize", []),
    }

    spec = run_role_skill(
        producer_for_artifact_type("TechnicalSpec"),
        architecture_decision={
            "artifact_type": "ArchitectureDecisionRecord",
            "chosen_option": {"id": "minimal_safe_extraction"},
            "spec_writer_brief": {"scope": ["bounded target"], "files_or_symbols": sources},
            "traceability": [
                {"source": source, "requirement": "Capability candidate requires TechnicalSpec."}
                for source in sources
            ],
            "source_context": context,
        },
    )

    contract = spec["extraction_contract"]
    ranked = {row["source"]: row for row in contract["ranked_candidates"]}
    assert contract["candidate"] == "pkg/core.py:normalize"
    assert "missing_runtime_sdk" in " ".join(ranked["pkg/optional.py:run"]["reasons"])
    assert ranked["pkg/optional.py:run"]["dependency_readiness"]["status"] == "missing_external"


def _context(symbol: str, missing: list[str]) -> dict:
    return {
        "kind": "pure_transform",
        "signature": {"args": [{"name": "value", "annotation": "str"}], "returns": "str"},
        "snippet": {"text": f"def {symbol}(value): return value"},
        "dependency_readiness": {
            "status": "missing_external" if missing else "ready",
            "missing_external_modules": missing,
        },
    }

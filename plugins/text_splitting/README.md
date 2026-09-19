# Text splitting helper competency

Version 0.1.0 owns `extract_splitlines_helper`: one syntactically recognized
`.splitlines()` call with no arguments, its recipe and proposal metadata/refusal.
Receiver type and real I/O semantics are not inferred by this mechanism.

Operations: `patch_recipes`, `propose_patch`, `propose_helper`.
Proposal inputs: source, origin_symbol, proposed_symbol. The old patch dict/null
and `helper_proposal.v1` are supported. Metadata is text_expression/split_line;
refusal remains splitlines_helper_pattern_not_proven. Recipe fields and algorithm
are preserved in one working owner. No runtime imports, source execution or
source writes occur in this plugin. It depends on the existing Inspect API.

Registry identity includes source, KB and the declared Inspect package. Runtime
owns admission, result validation, selection/ambiguity, sandbox, compile/write,
differential verification and source authority. Active lifecycle is not promotion.
The old extractor import delegates to the registered client without fallback.

Evidence: `docs/architecture/text_splitting_20260916.md`.
Tests: `tests/runtime/test_text_splitting_owner.py`,
`tests/runtime/test_text_splitting_contract.py`, frozen recovery packages and
existing helper extraction/role recovery suites.

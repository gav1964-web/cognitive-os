# JSON parsing helper competency

Version 0.1.0 owns `extract_json_loads_helper`: one inline `json.loads` around
a syntactically recognized `read_text` call, its recipe and proposal metadata.
This is source transformation, not a general JSON parser or a proof of I/O binding.

Operations: `patch_recipes`, `propose_patch`, `propose_helper`.
Inputs for proposals: source text, origin_symbol and proposed_symbol.
The legacy patch dict/null and the common `helper_proposal.v1` envelope are both
supported. Owned metadata is read_expression/parse_line; refusal remains
json_loads_helper_pattern_not_proven. The original algorithm and limits are preserved.

Local `knowledge/patch_recipes.json` is the single working recipe source;
registration binds code, KB and the declared Inspect implementation package.
The plugin has no runtime imports, source execution or source write authority.
Registry admission, common result validation, sandbox, candidate selection,
compilation, differential verification and source application remain outside.
Existing planning/research recognition remains unchanged. Network response
parsing, JSON serialization and text splitting are separate scopes.

Evidence: `docs/architecture/json_parsing_20260916.md`.
Tests: `tests/runtime/test_json_parsing_owner.py`,
`tests/runtime/test_json_parsing_contract.py`, shared full recovery package
fixtures and existing helper/role recovery regressions.

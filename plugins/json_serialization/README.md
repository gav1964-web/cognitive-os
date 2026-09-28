# JSON serialization helper competency

Version 0.1.0 owns the bounded `extract_json_dumps_helper` mechanism: one
`json.dumps(value)` directly inside a `write_text` argument, recipe limits,
proposal metadata and refusal. It is not a general JSON codec or parser.

Operations: `patch_recipes`, `propose_patch`, `propose_helper`.
The recipe is read from local `knowledge/patch_recipes.json`, with unchanged
fields and `automatic_source_mutation_allowed: false`. Registration permits
read-only calls and does not authorize source application.

Proposal inputs: source text, origin/proposed symbols, maximum_free_variables.
`propose_patch` retains the legacy patch dict/null result; `propose_helper`
returns `ok` and a `helper_proposal.v1` envelope with owned metadata/refusal.
No source execution, filesystem mutation or runtime import occurs here.
The installed recipe catalog checks registration and rejects duplicate IDs.
Shared AST navigation/parser comes from Inspect; its installed implementation
is included in plugin identity. Changed imported code requires restart.

Recovery owns selection, ambiguity, sandbox, compile/write and differential
verification. Existing planning recognition remains outside this plugin.
JSON loads/text splitting and JOSE semantic profiles are distinct scopes.

Evidence: `docs/architecture/json_serialization_20260916.md`.
Tests: `tests/runtime/test_json_serialization_owner.py`,
`tests/runtime/test_json_serialization_contract.py`, frozen recovery packages
and the existing helper extraction/role recovery suites.

Development verification: `plugin.json:test_paths` declares project-relative
owned test suites consumed by `tools/check_plugins.py`. This metadata does not
change runtime capability loading or grant execution authority.

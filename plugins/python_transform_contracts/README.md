# Python transformation contracts

This competency owns `python_text_to_valid_python.v1`, its applicability, bounded
bracket-layout variations and syntax oracle. Its KB is local. Inputs are an
explicit invocation and a source-bound valid Python seed. No project names,
source execution or production repairs occur in the plugin.

Each variation must preserve the input AST. The generated native tests require
the returned string to parse. This checks syntax, not semantic equivalence or
formatting correctness. Applicability is explicitly selected by the caller;
grammar mismatch is `not_applicable`, never a passing check. Native tests remain.
For formatting-only operations, explicitly choose `python_text_preserves_ast.v1`:
it additionally requires unchanged output AST. This is not applicable to imports
cleanup, code migrations or other intentionally semantic transformations.
Runtime owns snapshots, source binding, subprocess execution and result receipts.
Tests: `tests/runtime/test_owned_acceptance_properties.py`.

Version 0.2.0 adds opt-in `python_formatting_independent_fragments.v1`.
The caller supplies a no-op `seed`, a positive `preservation_seed` and its exact
`preservation_expected` output from the same bound native test source. All three
literal values are checked against that source before generated tests execute.
The positive example must pass twice on the unchanged baseline; a matching
literal alone does not establish a preservation requirement.
The plugin checks each example separately and both concatenation orders, with
exact output and AST preservation. This catches a whole-file rollback that
preserves syntax but suppresses required formatting in the other fragment.

Applicability must be explicit: independent module fragments in a local formatter.
Whole-module sorting, context-sensitive formatting and semantic transformations
are outside this contract. Positive examples must actually change the text;
AST-changing or invalid examples are not applicable. These examples do not prove
complete semantic adequacy or replace the original regression tests.
Tests: `tests/runtime/test_formatting_composition.py` and plugin contract tests.

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

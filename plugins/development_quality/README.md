# Development quality

Owns `development_quality.v1`: Architect state distinctions/counterexamples,
SpecWriter behavioral coverage and rejection of obvious constant assertions,
design/acceptance audits and independent challenger instructions. Knowledge and algorithms
stay here; runtime owns calls, copies, budgets and receipts. Static admission is
not a semantic proof. Unsupported UI/environment or inconclusive mutation evidence
must remain explicit. Consumers: `runtime/feature_quality*.py` and quality CLI.

Existing regression nodes count as preservation only when selected and grounded
in supplied source. A valid fault campaign is fixed while production hashes stay
unchanged; test extensions recheck it. Experimental cohort fixtures and grading
live under `tests/fixtures` and `evaluation`, outside model-visible target copies.
The same-model grader and deliberately small synthetic tasks cannot certify role
levels on large real projects.

Action `compare_draft(previous,current)` reports disappearing test functions and
methods, including loss within an unchanged filename. Uniquely named tests may
move between files. Intentional renaming/consolidation needs `case_replacements`
with existing replacement nodes and a reason; a fresh semantic auditor checks
the assertions. Bodies remain editable until accepted, and stable names are not
proof of preserved semantics. Runtime retains the fuller draft on unexplained
loss and requests correction before another paid audit. No target-specific rules.

Action `boundary_probes` returns at most eight exact AST comparison foils with
source hashes. They are unvalidated hypotheses: the existing challenger must
establish a user-goal violation with a native witness on discriminating valid
parameter combinations. Equivalent changes or masked predicate differences do
not count as defects. No project names or fixture-specific algorithms enter
production policy. Tests: `tests/test_boundary_probes.py`.

Version0.1.3 asks Architect to connect changed decisions to observable preservation
invariants and downstream consumers. SpecWriter supplies a small `contrast_pairs`
index linking executable positive/negative or boundary/control examples. Optional
pair metadata is checked for real, unambiguous new/selected test nodes; parameterized
cases are allowed. This structural check does not prove different public results:
for parametrized references it resolves the base test symbol, not collected case IDs.
The existing semantic auditor inspects assertions and native qualification still
runs. Missing metadata remains compatible with historical artifacts. Knowledge
explicitly rejects blanket rejection/empty-result fixes that pass only negative
examples. Tests: `tests/test_contrast_cases.py`.

Auditors must bind requested changes to the explicit user-goal boundary. A
pre-existing defect in an adjacent producer is separate debt unless its repair
is necessary for that boundary. Unsupported end-to-end claims should be narrowed;
they must not silently expand implementation and acceptance scope. This policy
also applies when an earlier audit introduced the expansion. The three-project
measurement and its retained failed attempt are documented in
`docs/architecture/roles_package_20260929.md`.

The sealed native evaluator accepts either the legacy single source string or
a mapping of production paths to contents for reference/original/mutants. It
copies all admitted candidate production files, including newly added helpers,
before running its separate oracle. Tests: `tests/test_multifile_evaluation.py`.
Evaluation fixtures and reference implementations never enter the live role
context. A successful small multi-module fixture remains a bounded pilot.

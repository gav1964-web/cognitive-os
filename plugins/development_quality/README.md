# Development quality

Version 0.1.23 admits only a model-authored correction of a legacy case-plan
label `feature_gap`/`feature_control` to `feature`/`boundary`, with identical
node/behavior and a matching unique qualified baseline classification.
The versioned `allow_qualified_label_correction` action grants no approval.
Runtime still binds the source, design and test bytes, journals the correction,
and reruns audit/native gates. Valid inherited labels, forecasts and assertions
cannot be changed through this exception. Historical transcript replay retains
its original restoration semantics unless it records `qualified_label_repair.v1`.

Version 0.1.21 defines how the auditor consumes `historical_audits`: re-evaluate
each old concern under the current goal/source/contract and report still-valid
defects as current issues. A changed policy neither resolves a counterexample
nor authorizes rewriting frozen tests. Runtime separates historical evidence
from active Writer demands and persists it across stops before a fresh audit.
See `docs/architecture/audit_feedback_20260930.md` for evidence and limits.

Version0.1.17 adds `assertion_inventory` and `validate_assertion_review` to
`development_quality.v1`. For unaccepted feature-gap tests, the inventory exposes
Python assert statements with location IDs and a digest of tests/predictions.
A strict quality audit must partition these assertions into changed behavior and
preserved invariants. Preserved assertions need separate nodes classified as
preservation; native qualification must execute those controls green on original
source. Whole-test `feature_gap` remains correct when one intended change makes
the original fail. The partition belongs to the auditor's response, not invented
SpecWriter metadata. Missing, duplicate, stale or invalid links block approval.
Audits receive `accepted_test_paths`: predictions for those tests are mandatory
baseline bookkeeping, including incidental controls. Narrowing goal claims does
not authorize deleting their forecasts or rewriting their accepted assertions.
After an auditor-policy change, resume may re-audit the exact rejected draft
against current source/goal bindings before requesting another Writer response.
Prior issues remain advisory and all admission/native gates still run. Known
Challenger variants also survive a resume from an unaccepted extension, bound
to the earlier candidate and reexecuted when its production hashes still match.
A complete paid draft stopped before its first audit may also be restored after
the same goal/source/design checks; this restores a proposal, never approval.
Restored audit feedback contains expanded test bytes, so output references do
not escape into another input context. Broken runtime input references stop the
cycle instead of requesting a Writer correction to infrastructure metadata.
Malformed approving audit partitions receive a bounded correction by the auditor
itself, without asking Writer to regenerate tests. If no equivalent control exists,
the auditor must reject with a real missing-test issue. Exhausted audit-format
repair stops the cycle; an invalid approval is never promoted.

The catalog does not infer semantics or prove that a linked control is equivalent:
that remains a semantic audit obligation. Indirect/helper assertions without a
located Python assert remain explicit limitations for ordinary review. Already
accepted frozen paths keep their original contract; they are not rewritten.
Consumers opting into `require_baseline_expectations` use this gate. Legacy
low-level callers retain their prior behavior and acquire no new assurance.

Runtime may restore only an omitted `content_sha256` from an unambiguous exact
`immutable_test_refs` entry. It records the raw proposal, restored metadata and
catalog; supplied wrong hashes, unknown paths, replacement contents and ambiguous
catalogs remain invalid. All subsequent byte identity/native gates still apply.

Version0.1.13 separates `baseline_expectations.classification` from
`case_plan.kind`. Baseline classification is preservation/feature_gap/feature_control;
coverage categories remain feature/preservation/boundary. Unambiguous legacy
baseline `kind` is still readable; conflicting old/new values are rejected.
The validate result adds `semantic_audit_ready`: only a missing coverage-category
label may accompany an otherwise executable draft into semantic inspection.
It does not grant admission: metadata, native, continuity, frozen-test and
behavioral-witness gates must still pass. Syntax/invalid-node issues block audit.

Policy asks the first semantic audit to examine all material obligations together,
retain covered assertions across corrections and distinguish actual source branches
from arbitrary input cross-products. Real omissions still require correction.
`role_output_limits.spec_auditor = 8192` caps only the audit response; runtime applies
the lower of this value and a positive caller limit before transport/reservation.
An unspecified caller limit uses the policy cap. SpecWriter and Programmer retain
their configured output capacity. The cap is supported by 14 observed audits
(maximum 4300 output tokens), not a guarantee for every future audit. Output
truncation cannot count as approval. Resource exhaustion ends the current runtime
cycle; it cannot be repaired by repeatedly routing the same candidate to a role.

Fresh evaluation: `docs/architecture/roles_fresh_20260930.md`. The fixed cohort
closed 0/5 tasks; two candidates passed sealed checks but remained incomplete.
These changes have regression evidence, not demonstrated end-to-end savings.

Version0.1.10 adds `revise_preservation_assertions` in contract
`development_quality.v1`: a pure proposal transformer for a disputed frozen
acceptance assertion. Input includes artifact, proposal, goal and sources.
It permits at most two distinct top-level test functions, changing only literal
expected values on the RHS of one equality per function. Goal/source quotes
must match supplied evidence; calls, operators, container shape/keys, fixtures,
test identities and other assertions remain unchanged. It grants no approval.
`spec_dispute_writer` and `spec_dispute_auditor` policies belong to this plugin.
Runtime must demonstrate preservation on original and candidate, preserve all
other native outcomes, obtain a separate digest-bound audit and rerun ordinary
qualification/review. Source-project regression tests cannot be revised through
this action. Unsupported or unclear conflicts stay blocked. An auditor is a
separate model invocation, not an independent model or certification authority.

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

Version0.1.4 binds new Analyzer evidence to supplied line ranges and exact
`quote` excerpts; an optional `symbol` must occur in the cited excerpt. This
checks traceability, not whether a causal claim follows from the quote. The
design auditor checks inherited semantic claims and requires corrections in
the design. Empty historical evidence remains compatible and grants no credit.

Reviewer may return behavioral `counterexamples` with `input`, `expected`,
`observed`, and `goal_clause`. A rejected, previously green candidate with such
evidence is routed to SpecWriter before another repair, including on resume.
The existing native witness gate requires added tests to assertion-fail on that
exact candidate; the semantic auditor checks that they cover the reviewed
defect. Frozen tests stay immutable. Documentation issues do not force a
behavioral witness. Tests: `test_source_evidence.py` and runtime
`test_feature_review_counterexample.py`, `test_feature_spec_witness.py`.

Citation diagnostics locate an exact unique quote only in supplied contiguous source
ranges; ambiguous or absent quotes receive a bounded numbered excerpt. The model
must correct its artifact; hints never grant acceptance or semantic proof.
Caller names in a design are impact evidence, not automatic authority to extend
the goal to an unchanged upstream pipeline. Required integration and changed
caller wiring still require tests; production replacement remains forbidden.
# Metadata repair (0.1.7)

Version0.1.8 additionally locates a unique exact Analyzer quote within supplied
contiguous source. It can repair its line range while retaining the quote and
finding verbatim. Ambiguous, absent or conflicting excerpts do not permit repair;
this proves location only, not semantic correctness. Runtime journals the original
artifact, source evidence and corrected range before ordinary admission.

`repair_metadata` may derive an absent `regression_policy` only from the complete
runtime-owned source inventory, an empty regression selection and a declared
preservation case. An existing suite, missing inventory or explicit value blocks
this derivation. It changes neither test content nor acceptance authority. The
runtime retains original/normalized values and hashes, then performs normal audit
and native qualification. Tests: `tests/test_spec_metadata.py`.
# Admission batching (0.1.9)

The spec auditor receives structurally valid drafts together with known continuity
issues, so independent semantic omissions can be reported in
the same correction. Earlier audit findings remain advisory history bound to the
same goal/design/source; fresh audit may reject unsupported demands. No audit
approval overrides structural, frozen-test, witness or native gates.
Changed frozen tests and an unmet required native witness still stop before audit.

# Per-case baseline predictions (0.1.11)

`validate_baseline_expectations` binds model-authored classifications to exact
goal/source excerpts. `compare_baseline_expectations` matches every native test
identity exactly once, with homogeneous parameter-family selectors or explicit
parameter IDs. Preservation and feature controls must pass; feature gaps must
assertion-fail under the runtime's independent native gate. Mixed/ambiguous,
uncovered, unused or overlapping predictions fail admission. Classifiers and
semantic audit instructions live here; runtime owns execution and receipts.
Neither action grants semantic approval. Exact quotes establish provenance only.

Quality CLI/file-worker require predictions for new specifications. Existing
Python callers remain compatible unless they opt into
`require_baseline_expectations=True`; supplied predictions are always checked.
Legacy frozen checkpoints retain their original contract. New specifications
must classify their complete merged suite without changing frozen test bytes.
No project-specific rules or automatic test expectation changes are introduced.

Experimental Python API audit_mode="on_feedback" schedules optional model audits through development_quality.audit_schedule.v1. Default "always" is unchanged. Native checks, source/write-scope integrity and final Reviewer are mandatory. Skips are journaled, never semantic approvals. Protocol: docs/architecture/paired_workflow_20260930.md; tests/runtime/test_audit_schedule.py.

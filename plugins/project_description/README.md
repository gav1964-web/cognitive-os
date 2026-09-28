# Project description competency

## 0.18.0: opt-in expanded review context

`--review-context-profile expanded` retains up to96000 serialized context characters
and32000 per ordinary source; explicitly requested excerpts retain their10000 cap.
The default32k/4k policy remains available unchanged. This addresses evidence lost
between draft and review, without changing acceptance or claiming semantic proof.
External request/token budgets still apply; callers must reserve the larger input.

## 0.16.0: bounded exception flow

The existing explicit-input/property analyzer now follows `try/except/else/finally`
over its Boolean/None and owned-dictionary domain. It distinguishes `ValueError`,
`TypeError` and `RuntimeError`, follows visible validator calls, and honors
finally-return overrides and mutations of returned dictionaries. A caught failure
returning an error status is not a successful invocation. An omitted argument can
still succeed when the implementation supplies a usable default.

Unknown calls, exception bindings, other exception types, bare re-raise and
unsupported expressions remain unknown. Finally cannot erase an analysis gap.
This extends the existing opt-in property contract; it does not automatically
understand arbitrary project code, rewrite full descriptions, or certify natural
language claims. Fresh contrast tests compare literal fixtures with CPython.

## 0.13.0: independently bound normal-return property

`prepare --return-property property.json` opts a v4 claim into a property fixed
before the model response. The selector contains `path`, `symbol`, `field`,
`claim_start`, `claim_end` (exclusive), and `kind`: `normal_return_field_true` or
`describes_diagnostic`. The reviewer owns the mapping from text to property;
the model cannot bypass it by calling a guarantee a diagnostic.

The plugin reads current hash-bound source and explores small pure functions
over Boolean/None positional inputs (up to six parameters and 64 combinations), including branches, early returns,
owned dictionary updates, raises and visible local function calls. Unsupported
syntax, missing helpers, recursion, missing fields and non-Boolean conditions
cannot establish the property. Fallthrough and zero normal returns do not count
as a positive proof. Source code is never executed by this analysis.

The response schema remains v4 parts/coverage/proposed_text. For bound guarantees,
supported parts are lowered to uncertain unless the property holds in the model.
Other verdicts and text outside the selected span are preserved. Analysis does
not infer the correctness of the selected property or arbitrary input types.
Raw responses, property, model assumptions and guard decisions remain separate.
Jobs and proposals recheck current analysis and reject tampering even if the
outer digest is recomputed. This mode is separate from suffix/mechanism modes;
default full-description behavior is unchanged.

## 0.12.0: explicit mechanism bindings and consistency

`prepare --mechanism-review --return-flags selectors.json` opts a v4 job into
`claim_mechanism.v1`. The response adds one mechanism record per text part:
subject, scope, intent, basis and exact path/symbol/field bindings. Only existing
analyzed fields are accepted. Old v4 jobs and default full-description review
retain their prior contracts.

The plugin conservatively lowers supported parts to uncertain when a declared
guarantee relies only on a suffix allowing false return, lacks a binding, or
claims more scope than the suffix. It never promotes a conditional trace to an
executed counterexample. A guarded suffix does not cover early returns in the
unmodeled prefix; only explicitly suffix-scoped assertions fit that basis.
Claims relying on other visible enforcing code remain cited model opinions.

Raw responses and original verdicts are preserved alongside the consistency
audit. Wrong classification (for example treating a guarantee as reporting),
wrong semantic predicate binding, or an invented interpretation of a real quote
can still evade this check. Valid structure is not semantic certification.

Measured 2026-09-18: experimental opt-in only; do not promote this mode to the
default. Effective controls matched2/5, versus raw part opinions4/5. Original
Replay guarantee remained supported; specific wording worked in both modes.
The gate added false uncertainty and a contract rejection without fixing the
main error. [Measured limits and next work](../../docs/architecture/mechanism_review_20260918.md).

## 0.11.0: conditional return-flag evidence

The `return_flags` action reads hash-bound complete Python functions and models
a narrow terminal dictionary/Boolean/raise fragment without executing source.
It distinguishes a reported false flag from rejection before normal return and
provides nearby integer examples for supported comparisons. At most three
functions, six predicates per function and 12000 analysis characters are allowed.
Independent predicate values and entry to the suffix are assumptions: conditional
witnesses do not prove full-function reachability or whole-project guarantees.

V4 claim jobs can opt in through `prepare --return-flags selectors.json`, a list
of `{ "path": "module.py", "symbol": "function" }` selectors in job sources.
Jobs rederive the evidence and require `return_flag_scope` coverage. Full
description review adds this evidence after Python-function lookup without
another model request. Unsupported cases stay explicit; semantic truth is not
automatically certified. Knowledge and the finite model belong to this plugin.

Four tiny live controls were correct, but Replay still asserted the false
guarantee even while acknowledging possible false diagnostic flags. Aggregate
uncertainty came from a different missing binding. The assistant rejected that
proposal. See [measurement and limitations](../../docs/architecture/return_flags_20260917.md).

## 0.10.0: requested workflows, final assertions and documentation conflicts

The32k review budget reserves complete explicitly requested excerpts (up to10k
each) before supporting text. Exact complete helper sections from the same hashed
file can share one visible copy via `covered_by`; truncated or changed sources
cannot alias it. Exhaustion remains explicit. This is evidence availability,
not proof that a model will interpret the evidence correctly.

The lookup catalog presented to review now includes only supported code/README
paths. Other collected metadata remains evidence but is not advertised for lookup.
README remains `documentation_claims`. Claims without implementation citations are
marked in the rendered brief and cannot enter accepted product_context. A code
citation alone does not establish truth: caller review remains necessary. COS does
not automatically rewrite a stale README or reliably detect every contradiction.

`tools/review_description_claim.py prepare --namespace final` prepares a v4 job
from the edited final description. The default remains `draft`; v1-v3 retain that
scope. Report digests and exact original claims bind proposals to their namespace;
final proposals do not close draft tasks with the same claim ID. Saved legacy
jobs keep their original instructions and payloads.

Measured limits: the conflicting-README fixture did not produce invented XLSX or
cloud features, but omitted the zero-value boundary. Replay's full and focused
reviews still asserted an unenforced guarantee despite visible checks. See
[the stage report](../../docs/architecture/workflow_review_20260917.md).

Collects bounded, read-only source evidence and owns the explanation policy in
`knowledge/description_policy.json`. Does not execute project code or call models.
The registered runtime coordinator calls the configured DeepSeek/fallback route
for a draft and a separate factual review, validates claim references, checks source
hashes between stages and writes no project files. A failed review does not publish
the draft. This costs two or three model requests; transport fallback can add attempts.

Python files over the excerpt budget first compact large embedded string literals,
retaining executable syntax and visible HTML text. If still over budget they retain
module headers, excerpts from function bodies (including late definitions) and UI text. Generic
text files retain their beginning and ending. Limits and omitted sources are explicit.
Entrypoints and directly referenced local scripts receive more context than
auxiliary files. When an entrypoint is available, README contributes declared
purpose only, not unverified installation/feature claims. Literal input-format calls and conditional predicates survive
body abbreviation. Identical files are deduplicated by bytes, without assuming installation-folder
names or declaring an active root. Private configuration/environment files are
excluded; common literal credentials are redacted. This is not a complete secret scanner.

The resulting contract separates purpose, user scenarios, data flow, unknowns
and evidence references. It is a product brief, not a speculative limitations audit.
Owner statements are distinct from source facts and are not sent to the model.
An exact syntax index highlights route literals, CLI arguments, file globs and
visible UI text without inferring a domain label. Owner notes render verbatim in
a separate section; model claims can cite only source IDs, never owner IDs.
Reference validation does not prove semantic correctness: a human or independent
evaluation must review the claims. Provider failure yields a failed receipt,
never a fabricated project narrative.

Run from the COS root:

```
python tools/describe_project.py --project-dir /path/to/project --output artifacts/description/report.json
```

Use `--owner-note` for explicit product facts supplied by its owner. The previous
architecture-analysis route retains its existing behavior; this competence is the
entrypoint for human-facing product descriptions.

The dedicated `project_description` model profile uses `deepseek/deepseek-v3.2`
with a 120-second request timeout and the configured GigaChat fallback. Other
routes keep their existing profiles. `COGNITIVE_OS_DESCRIPTION_MODEL`,
`COGNITIVE_OS_DESCRIPTION_BASE_URL`, `COGNITIVE_OS_DESCRIPTION_API_KEY_ENV` and
`COGNITIVE_OS_DESCRIPTION_TIMEOUT` allow task-specific overrides. The model and
endpoint also respect explicit L4.5 environment overrides when no description
override is provided. CLI `--timeout` overrides only the primary request timeout.

Policy 0.1.1 derives scenarios from evidence without domain-specific checklists.
Known map errors are evaluation-only examples in
`tests/fixtures/project_description/map_regressions.json`; they are not model input.
No project name selects an instruction variant. Collection still has explicit
language and layout limits; this is not a claim of universal project coverage.

Collection prioritizes conventional source trees over auxiliary tools/tests and
recognizes entrypoint filenames within `src/` and shallow HTML entrypoints.
Primary files and explicitly imported symbols share the context budget after
reserving space for the other selected files. Function sections share a bounded
budget before rendering, with priority for symbols imported by application code.
Late definitions therefore cannot be crowded out solely by a long module header.
These are layout heuristics, not proof of the active application root.

## 0.2.0: dependency context and bounded review

Static Python imports and local HTML/JS references link entrypoints to supporting
files. The bounded catalog records source hashes and symbols; auxiliary scripts
are marked explicitly. These edges are syntactic candidates, not proof of a call.
The model review may request at most three hash-bound excerpts in one additional
round. Private/outside paths, stale hashes and a second request round are rejected.
Thus a description costs two or at most three model requests, plus transport fallback.

Final reviews account for every draft claim. Published claims require valid source
IDs. Removed claims without evidence are recorded as unverified removals and shown
as completeness questions; this does not certify semantic correctness. A failed
review still does not publish the draft. The live VR trial exhausted the lookup
round; the gateway trial still lost real workflows. More context is not yet a
proven general quality improvement; saved failures remain part of the evaluation.

`tools/plan_from_description.py` accepts an explicit review and task contract to
carry selected claims through Analyzer, Architect and SpecWriter as advisory
context. Every stage checks project identity, content digest and current source
hashes. Requirements and execution authorization remain separate.

Review requests include the completed lookup history and an explicit final-response
requirement after that round. Repeated requests still fail without another read or
model call. Every removed or rephrased draft claim is retained in `review_changes`
with its original text, references and review reason; downstream `review_gaps`
carry these as unverified changes, separately from accepted product facts.
These mechanisms improve traceability; they do not establish semantic quality.

## 0.3.0: claim evidence and review audit

The `review` action accepts saved evidence and draft claims. It returns a bounded
evidence view and claim packets containing exact quoted-value occurrences, source
hashes and offsets into saved excerpts. Literal presence never proves a workflow.
The JSON evidence+packet context is capped by the plugin-owned `claim_review`
policy; draft text and system instructions are additional request overhead.
All source IDs remain available, while excerpts and the discovery catalog can be
shortened. The full receipt remains intact for provenance and offline checking.

Optional `reviews` enable mechanical checks of explicit `literal_absent` assertions.
When supplied, `review_evidence` binds these checks to what the reviewer actually
saw. Text found only in the larger saved context cannot contradict an absence
assertion scoped to the visible excerpt. Legacy removed-claim reasons are checked
for quoted values appearing in code; overlap creates a review task, not a semantic
verdict. Documentation mentions are not treated as code matches.

Runtime records draft-scoped `review_tasks`, including unfinished claims when review
times out. Accepted product facts stay separate. Tasks reach Analyzer, Architect
and SpecWriter through advisory product context without execution authority.
`python tools/audit_project_description.py --report saved.json --output audit.json`
prepares the same evidence and tasks without a model, rejects stale source hashes,
and refuses to overwrite the original report. Source text is never executed.

## 0.4.0: single-claim proposals

`claim_review` prepares exactly one claim with a 12000-character evidence+packet
budget. Optional `claim_result` validates a supported/refuted/uncertain verdict
and exact source quotes; it does not certify the conclusion. Unsupported source
IDs, invented quotes and affirmative verdicts without citations fail validation.
The dedicated instruction remains plugin-owned and domain-neutral.

`tools/review_description_claim.py prepare` binds a job to the original report,
source hashes and optionally up to three explicit catalog lookups. `run` makes
one model request with no fallback/retry; it rechecks source hashes before and
afterwards. `attach` associates proposals with an offline audit without changing
accepted facts or closing tasks. Explicit product-context review can carry these
proposals through the planning roles; each stage revalidates sources and citations.
All receipts retain semantic_verified=false and execution_authorized=false.

## 0.5.0: obligations, counterexamples and explicit decisions

V2 jobs use `single_claim_review_job.v2` and the plugin action `claim_review_v2`.
The model must split the claim into 1-8 verbatim parts whose ordered concatenation
equals the entire original text. Every part has its own verdict, reason, citations
and counterexample citations. The plugin derives the overall verdict from these
assessments: a refuted part or declared counterexample makes it refuted; missing
required context or uncertainty prevents supported. A global refutation without
a refuted part is inconsistent and fails. Original responses remain in receipts;
normalized results retain model_verdict and an aggregation explanation.

Coverage requirements are frozen in the job. Defaults cover conditions/scope and
bindings between names, entrypoints, callers, implementations and configuration.
`prepare --coverage requirements.json` accepts 1-6 custom id/description objects.
Each needs a shown/missing/not_applicable assessment, with exact quotes for shown.
Optional `--requests` still reads at most three catalog-bound source excerpts.
No extra model lookup or automatic source execution is introduced. Names and
comments alone cannot establish a connection. This is a reporting obligation,
not an AST proof: a model that hides a counterexample or falsely claims sufficient
coverage can still be wrong. Text coverage does not prove atomic decomposition.

V1 jobs keep their saved instruction/contract and 1600 output-token cap. V2 uses
a 3200 output-token cap for the structured answer; both make only one request,
with no retries/fallback. This cap change is not a measured cost improvement.

`decide --proposal receipt.json --disposition accepted|rejected|deferred
--reviewer NAME --reason TEXT [--accepted-text TEXT] [--ledger previous.json]
--output next.json` records a separate reviewer attestation. Acceptance requires
the exact proposed correction, or the original text of a supported claim.
History is linked by digests and checked against current proposal sources; it is
not signed identity or independent certification. A new output path preserves
earlier receipts. Decisions can accompany product context through planning roles,
but do not rewrite its accepted facts, close tasks or authorize execution.

`tools/prepare_claim_obligation_suite.py` freezes five authored synthetic cases
without inference. Expected answers remain in the evaluation protocol, outside
model messages. Offline contract tests are not live semantic evaluations.

## 0.6.0: lean claim review and package token budget

V3 jobs use `single_claim_review_job.v3` / `claim_review_v3`. Responses
contain `parts`, a `coverage` object keyed by the frozen requirement IDs, and
optional `proposed_text`. Each part has text, verdict, reason and exact citations;
ordered part text must still reproduce the entire claim. Coverage records have
status, reason and citations. `contradicted` distinguishes an evidenced conflict
from `missing` context. Shown and contradicted coverage both require exact quotes.
The model no longer repeats a global verdict, reason, citations or counterexamples.
Code derives the verdict: any refutation/conflict wins, otherwise uncertainty or
missing context prevents supported. Semantic correctness still needs review.
V1 and V2 retain their saved contracts; V3 keeps the 3200-token output cap.

`runtime/claim_review_replay.py` explicitly projects saved V2 answers onto V3 for
offline diagnostics. It preserves original receipts and yields a separate replay
artifact that cannot pass the model-proposal gate. This is not a fresh model result.

V3 frozen suites require `--token-budget` pointing to a shared package ledger.
Reservations for all jobs must total strictly below 1,000,000 tokens. The reserve
uses serialized UTF-8 bytes, the output cap and a framing/gateway margin; it is not
a provider-attested billing ceiling. Each call is marked started before inference,
then settled from reported total input/output usage. Unknown usage stops remaining
calls across all suites sharing the ledger. The runner makes no retries or fallback.
The owner's standing authorization covers new packages below that threshold;
closed historical series are not resumed. This ledger counts COS calls only,
not the development assistant's session token usage.

## 0.7.0: explicit boundary alignment and claim-specific bindings

New jobs default to `single_claim_review_job.v4` / `claim_review_v4`. The response
shape stays the same as V3. Only ASCII whitespace at boundaries between parts can
be aligned to the original claim. Words, punctuation, order and whitespace inside
a part must match exactly. Invented separators inside a word or number fail.
The receipt keeps the raw response, normalized parts, character spans and every
changed boundary. Proposal revalidation checks that record as well as the verdict.
V1/V2/V3 contracts and historical failures remain unchanged.

The V4 instruction distinguishes a visible call from evidence of the connected
implementation. A claim about target behavior needs both the binding and target
code; a claim only about the direct call does not. This is still a model judgment,
not an AST proof or a certification of runtime dispatch.

`runtime.budgeted_chat.BudgetedChat` extends the shared package ledger to adaptive
description requests. Predeclared slots cap serialized input bytes and output
tokens. Actual messages and started status are persisted before each call;
telemetry is forwarded to the description receipt and settled in the same ledger.
Extra calls, fallback configurations, oversized messages and unknown usage stop
the sequence. Slots bound future requests without pretending their contents are
known before the model produces a draft. Normal description generation is unchanged
unless this explicit budget adapter is supplied as `chat`.

## 0.8.0: preserve helper context within the existing review budget

Review still has a 32000-character evidence+packet ceiling. Cited implementation
sources and requested excerpts receive more space than auxiliary tests/docs;
unused shares are redistributed, with a 4000-character per-source ceiling.
Python selection retains supplied function sections and same-file helper candidates
before falling back to character windows. Existing abbreviated sections keep their
omission markers; selection never invents missing bodies or reads new files.

A symbol lookup of a top-level Python function now includes up to six same-file
helpers found through direct unshadowed name calls, transitively, within the same
10000-character response limit. Arguments, local assignments/imports and nested
scopes are not treated as module helper bindings. Duplicate names are excluded;
cycles terminate. This is syntactic context, not proof of runtime dispatch.
External imports and attribute calls are not resolved. Hash/path/private-file
checks and credential redaction remain mandatory. Line ranges, omitted helpers
and caller truncation are explicit in `helper_context` and lookup history.
# 0.14.0: explicit API inputs (opt-in)

The existing `return_property` action accepts a second selector shape:
`kind: normal_return_for_inputs`, `inputs: {}` (or named Boolean/None values),
plus `path`, `symbol`, `claim_start`, `claim_end`. It uses `inputs` instead of
`field`. The coordinator binds the source hash as before. An empty input object
means a keyword invocation with all arguments omitted; visible literal defaults
are bound before checking the body. Required missing arguments and modeled raises
are counterexamples. Unknown dependencies and unsupported syntax remain unknown.

This checks normal return for one invocation in a bounded pure Python model;
it does not certify a working environment, output quality, or side-effect safety.
Default/keyword-only handling is limited to the selected entrypoint, with Boolean
or None defaults; helper signatures retain the earlier conservative restrictions.
Saved v4 property jobs keep their old instructions and analysis. This remains an
explicit reviewer operation; default full-description generation is unchanged.

## 0.15.0: successful result criteria and API source facts (opt-in)

`return_field_equals_for_inputs` requires `inputs`, `field` and `expected` in
addition to the bound source/function/text span. The finite model checks exact
value and type on the returned dictionary; `expected` is a string, Boolean or
None. Returning an error dictionary normally does not meet a success criterion.
The reviewer owns the criterion's meaning. Unknown calls remain unknown; no
automatic claim of successful external effects is made.

The `api_contracts` action accepts current hash-bound `evidence` and 1–3 `requests`
selecting top-level function entrypoints. It returns defaults, raising guards,
exception handlers, return/dictionary excerpts and syntactic call bindings within
the supplied Python files. Relative/absolute `from` imports and aliases can bind;
unknown imports, attribute dispatch and shadowed names remain unresolved. Source
is never executed. Quotes, traversal and total size are bounded and omissions
explicit. This map supports review; it is not proof of reachability or success.
The default full-description route is unchanged pending paired outcome evidence.

## Full-description behavior context (0.17.0)

`describe_project(..., behavior_checks=[...])` optionally supplies up to six
reviewer-selected `{path, sha256, symbol, inputs, field, expected}` observations.
The plugin's `behavior_checks` action checks one explicit keyword invocation per
selector using the existing bounded Boolean/None evaluator and complete same-file
helper context. Each fact cites an already collected source ID. Unknown calls and
incomplete context remain unknown; inspected code is never executed.

Both writer and review receive identical facts and plugin-owned interpretation
instructions. Selection is explicit, not automatic claim extraction. The receipt
records `claim_binding=not_established`: neither successful evaluation nor
`status=described` certifies the natural-language description. The September 18
paired experiment still produced a false default/guarantee in one final text.
This opt-in context has not established a general quality improvement.

Development verification: `plugin.json:test_paths` declares project-relative
owned test suites consumed by `tools/check_plugins.py`. This metadata does not
change runtime capability loading or grant execution authority.

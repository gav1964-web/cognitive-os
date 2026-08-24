# Cognitive OS Self-Improvement

## Principle

A project that falls below the required role score is a training example. Cognitive OS diagnoses the failure,
changes only bounded role parameters, reruns the same unchanged evaluator, and records what the experiment proved.
The source project, score threshold, evaluator, role caps, and active knowledge base are not trainable parameters.

## Loop

1. Run the three foundation roles and take the minimum role score.
2. Ask the local L3.5 profile for a structured diagnosis.
3. Escalate once to the external teacher only when the local result fails, is uncertain, or is not actionable.
4. Test a configured bounded set of source candidates already discovered by the deterministic analyzer, taking one candidate from each structural/name family before spending budget on near-duplicates.
5. Select the best attempt using measured role scores, never an LLM claim.
6. Stage the measured experience as a KB candidate and run post-training admission with the best confirmed challenger.
7. If the hypothesis is portable but evidence is still insufficient, build a `HypothesisValidationPlan` and ask the configured discovery capability for a bounded reserve of unseen similar Python projects.
8. Probe the reserve, retain the configured matching projects, and require at least one newly discovered match. Train the new holdout first while prior matches act as regression evidence. A policy may be promoted only after earlier projects supplied repeated evidence.
9. Re-evaluate the original corpus. Roll back every changed promotion path when the corpus gate finds a regression or no attributable improvement.
10. When several target choices produce no gain, stop target search and propose a reusable semantic contract profile or a typed capability-development request.
11. Synthesize at most one temporary profile from AST evidence, evaluate it in an isolated context, and discard it after the trial.

Foundation field trials close the same bounded executable-feedback loop as the production role workflow. An actionable
acceptance or eligibility rejection returns the target to Architect, rebuilds the role artifacts, and reruns acceptance
within `first_slice_reselection.execution_feedback_max_iterations`. Every attempted target remains in the report. If no
candidate reaches callable evidence, the loop returns the strongest safe intermediate handoff instead of the last trial,
so self-correction is monotonic with respect to measured downstream evidence.

A shadow trial may clamp evaluation to an existing candidate, but it must not override deterministic first-slice
viability evidence. Candidates marked as requiring reselection are excluded from discriminator trials even when an LLM
recommends them or a forced run would raise the score. This prevents lifecycle wrappers and no-op callables from
becoming measured "improvements" merely because they are easy to execute.

External adapter evidence is contract-scoped. A safe stdlib base may be preserved only when listed in
`source_isolation_policy.preserved_stdlib_class_bases`; external clients and transports remain fakes. Direct network
effects require both a matching entry in `foundation_evidence.process_isolated_direct_effect_profiles` and an isolated
process run. A target outside that contract family remains blocked even when a forced callable probe could execute it.

The small hypothesis holdout and the large blind corpus have different jobs. The bounded hypothesis holdout is an
active learning step selected from the portable failure class and structural signature. It answers whether one concrete
hypothesis generalizes. A 20-40 project multi-type blind corpus remains a release/calibration exam and must not be
reused as routine training evidence for every hypothesis.

Project discovery is a replaceable external capability. The current CLI adapter uses the ordered provider chain
`GitLab -> GitHub`, records every provider attempt, freezes selection and commit metadata under
`artifacts/hypothesis_holdouts/<hypothesis_id>/`, and excludes every previously selected repository across both forges.
Provider timeout, rate limiting, or candidate shortage triggers the next provider. An empty result from functioning
providers is frozen as an empty round and permits the next bounded round. Only unavailability of every provider
produces `HypothesisValidationTrial.status=blocked` with `reason=external_discovery_failed`; it is not recorded as a
failed technical hypothesis.
When a complete reserve lacks the configured total or newly discovered matches, the orchestrator starts another bounded round as
`<hypothesis_id>_rN`, carrying all probed projects into `excluded_projects`. It stops immediately after enough matches
or after `maximum_discovery_rounds`. Discovery, probe and training transitions are emitted through the trial progress
sink, and individual probe failures remain explicit evidence instead of crashing the complete trial.
Each round advances `search_page_start` by `maximum_search_pages`, so repeated rounds inspect disjoint provider windows
rather than the same highest-starred repositories.
Query-specific search cursors also survive `plan_version` changes. They read durable
validation reports for the same normalized class/signature, resume each old query
after its last consumed page, and start new vocabulary at page one. Bounded query
batches rotate between rounds instead of forcing every expression through one
shared cursor.
`provider_policy_overrides` applies only to adaptive hypothesis discovery. It may widen metadata eligibility without
changing the large release-corpus policy, evaluator thresholds or admission gates.
Provider query syntax is adapted at the boundary: GitHub qualifiers remain intact,
while GitLab receives equivalent plain search text.
Before external discovery, the trial loads exact prior probes for the same class and portable signature from durable
validation reports. Their paths must remain under `artifacts/hypothesis_holdouts`; each is re-probed under the current
evaluator and only a still-matching result is reused. Search-policy evolution therefore does not erase evidence or
reintroduce the same repository into network discovery.
An individual failure is recorded with `status=probe_failed` and its bounded error text.
The query planner composes effect and output-basis terms first, then interleaves
their individual portable-signature terms from
`hypothesis_holdout.signature_query_terms`, then uses the failure-class profile as
a bounded fallback. Signature vocabulary belongs in policy/KB, not role code.
Metadata search deliberately optimizes recall, not proof. Each round may freeze a
wider candidate pool, clone it, and run the configuration-driven AST pre-screen in
`runtime/hypothesis_structural_screen.py`. The screen reuses source-contract
inference to rank effect/output-basis evidence, excludes configured non-product
directories, freezes its shortlist as `structural_screen.json`, and sends only that
bounded shortlist to the expensive full probe. A new screen algorithm requires a
new `plan_version`; a repeated trial ID reuses the frozen shortlist.
`HypothesisStructuralScreenReport` is retrieval evidence only. It cannot satisfy a
failure-class match, raise a role score, train a project, or authorize promotion.
Portable-signature normalization is also policy-defined. Semantically equivalent
output evidence, such as implicit no-value return and explicit `None`, may share a
`void_side_effect` family without erasing the raw probe basis. Durable reports are
re-evaluated through the current normalization, so a formerly near-matching probe
can become reusable evidence after an explicit `plan_version` change.
Each plan also carries a structured `FailureDiagnosisEnvelope`: failure class,
required effects, effect matching mode, output family, and accepted raw output
bases. Full probes classify signature evidence as `exact`, `compatible`,
`near_contrast`, or `unrelated`. Only the first two can train; near contrasts remain
durable negative evidence. `recovery_metrics` reports matching yield, signature
discrimination, same-class count, and contrast signatures without converting those
diagnostics into a role-readiness score.
Policy may mark additional effects such as filesystem/database writes, network, or
process control as forbidden for a hypothesis. Such a project becomes a contrast
even when it contains every required effect; this prevents a broad subset match
from training on a known higher-risk boundary.
When a re-probe loses the redundant diagnosis class but retains a classified
baseline signature, validation restores the class from that signature. The effect
and output-family gates remain unchanged; an unclassified signature cannot use this
recovery path.
Keyword similarity and a broad failure-class match do not count as hypothesis evidence. A class/signature mismatch is recorded in `probe_results`, and
too few total matches produces `reason=insufficient_matching_holdouts`; no fresh match produces
`insufficient_new_matching_holdouts`. Neither state trains unrelated projects. Every
trial is persisted as `artifacts/self_improvement/hypothesis_validation_*.json`, including blocked trials.
When repeated class-and-signature-matched holdouts exhaust bounded search, the trial decision becomes
`capability_development_required` and carries a typed `CapabilityDevelopmentRequest`.
The same decision is required when at least three projects in one normalized family
cannot produce a candidate-selection challenger and at least one independent case
proves `no_structural_discriminator`. The requested capability is then a bounded
`candidate_selection_discriminator_plugin`, not another vocabulary patch.

`ImprovementPluginFoundryReport` resolves such requests against registered plugin capabilities. The
`candidate_selection_discriminator` plugin tests only Analyzer/Architect/SpecWriter-discovered targets, including
ranked candidates, reselection targets, and ADR first-slice targets. A shadow result is treatment evidence even when
it is not yet a durable promotion. Post-training admission consumes that frozen measured effect instead of rerunning
an unstable A/B trial.
The cycle orchestrator passes a confirmed shadow challenger and its frozen control/treatment pair to later admission
plugins in the same cycle. Plugins remain isolated and do not call each other. Structural synthesis keeps the smallest
shared discriminator; a low-arity rule is rejected and rolled back when ordinary routing selects a different candidate
than the measured shadow, even if the shadow itself reached the target score.
Recovery ordering prefers side-effect-free, receiver-free callables before dependency readiness because executable
isolation can stub bounded imports while receiver construction remains a separate proof obligation. Constant-return
policy hooks are structurally marked and cannot become strong first slices merely because they are easy to execute.
Support-path exceptions require a declarative AST contract family with an explicit `benign_support_path` decision.

Candidate-selection policy synthesis compares failed and successful contracts pairwise. It may learn a persistent
removed effect such as `memory_state`; it does not require every successful candidate to be side-effect free.
Promotion requires regression projects. The admission plugin snapshots promotion state, evaluates the controls,
applies the policy, and rolls it back on any score or status regression. A config-bounded sequence of evidence-derived
refinements may add execution-cost, dependency, argument-shape, or effect discriminators. Conditions that must hold
for every OR branch are stored as `common_requirements`; exhausting the refinement budget rejects the policy.
Each regression project is re-evaluated the configured number of times. Hypothesis discovery clones its frozen pool
with bounded parallel workers and isolates individual clone failures.
Before regression evaluation, the promoted policy must also reproduce the measured treatment through the ordinary
untargeted role route. Holdout reproduction and regression controls use the same full execution-feedback evaluator as
the outer corpus gate. A structural family is applicable only when its preflight trigger matches the failed control,
the control does not satisfy its successful requirements, and the measured challenger does. Missing shadow evidence
is enriched through the same static dependency and viability analysis used by Architect; unknown is not treated as a
negative discriminator.
Legacy policies without an activation state remain quarantined until revalidated through `reproduction_trial` and
then explicitly moved to `active` after ordinary-route reproduction passes.
During revalidation, the current project's staged contrast is holdout evidence only and is removed from every
training family before the repeated-case count is evaluated. Full measured `failed_contract` and
`successful_contract` records remain authoritative when the compact runtime score report omits structural fields.
An inactive legacy policy whose forbidden output can never trigger its preflight may be repaired only inside the
revalidation candidate; the repair, fresh holdout, ordinary-route replay, and regression cases are recorded together.
When an active or reproduction-trial policy selects a source-backed target outside the old Architect slice, the
Architect artifact is revised to own that same target before semantic scoring. The policy identity is carried through
`TechnicalSpec.extraction_contract`, and executable admission remains bounded by
`foundation_evidence.promoted_selection_policy_admission`; policy selection alone cannot waive effect, source-body,
state-mutation, or process-isolation checks. Architect may consume configured Project Analyzer `analysis_tasks` while
expanding its candidate window. A deferred callable remains closed unless an active learned policy explicitly marks it,
and that policy provenance survives the bounded execution-feedback rebuild.

Checkpoint reuse is tied to the self-improvement engine fingerprint. Changes to runtime or policy/config inputs
invalidate stale attempted-project state, so a repaired engine can retry the same failed corpus without manual artifact
deletion.

Foundation executable evidence may exercise direct in-memory state transitions only when the acceptance runner uses
a separate process and every declared and observed effect is allowed by
`foundation_evidence.process_isolated_direct_effects`. This permission does not cover filesystem writes, network,
database, or subprocess effects. Resource-return methods are classified by both method name and class owner, so an
object-pool `release_*` transition is not confused with project release/build support.
Repeated isolated-process timeouts use the config-owned execution-feedback resource limit. Reaching that limit stops
further target retries while preserving the best role artifacts, rejection history, and executable failure reason for
the next self-improvement cycle; the outer field-trial watchdog should not erase that diagnostic state.
Source-isolated method fixtures also infer numeric receiver fields when the method body proves their use in a
configured numeric call or arithmetic expression. The sample value remains policy-owned; unknown receiver fields do
not become arbitrary numbers.
Required receiver mappings align their fixture key with the same parameter sample used by executable acceptance.
Source isolation may replace a missing standard-library symbol only through an explicit
`source_isolation_policy.stdlib_import_fallbacks` entry. Chainable parameter protocols are likewise fixture-bound by
`structural_sample_policy.attribute_samples.callable_protocol_fixtures`; a source annotation must survive first-slice
normalization before an otherwise unknown object protocol can be treated as declared.
Inherited stdlib method contracts may bind argument fixtures through
`structural_sample_policy.attribute_samples.inherited_method_fixtures`. The active logging formatter recipe maps a
`logging.Formatter.format(record)` boundary to a real, sandboxed `logging.LogRecord`; it does not authorize arbitrary
attributes proposed by an LLM. The corresponding first-slice exception lives in the architecture KB and is limited to
the record-to-text formatter contract with ready dependencies and bounded `memory_state` mutation.

Temporary profiles cannot contain numeric score or ranking bonuses. They may only supply a typed contract family that
removes an unprofiled-target cap when source evidence proves every recognition gate. A successful profile is generalized
into a staged template and still requires independent cases and admission before it can enter active knowledge.
Raw `KnowledgeCandidate` records are never merged automatically. Separately registered improvement plugins may
auto-promote only their narrow allowlisted policy/config targets after repeated evidence, an independent holdout,
unchanged source projects, no role regression, and the normal corpus rollback gate.

Independent validation keeps recognition coverage separate from treatment evidence. A project that matches the AST
recognizer but already scores `9.7+` proves portability of the classifier only; it does not count toward the three
confirmed improvement cases required for review.

Bounded parameter strategies also keep evidence separate by diagnosed strategy. A URL-shape failure, missing instance
state, inherited-method failure, and directory-shape failure cannot satisfy one shared promotion threshold merely
because all produced `meta_only` executable evidence. Disabled strategies such as `absolute_url` become trial-eligible
only after three independent cases identify that same strategy; URL samples use a local `data:` value so recognition
does not authorize live network access.

If bounded discovery exhausts its original signature but at least four aligned, below-target holdouts converge on one
different exact signature, validation may redirect the existing prepared probes to that emergent hypothesis. The
redirect changes neither scores nor promotion gates. Candidate-selection shadow trials are failure-class scoped:
contrasts learned for `side_effectful_target` cannot satisfy admission for `executable_sample_contract` merely because
both failures emitted `meta_only` evidence.

Admission also partitions each failure class by its exact structural discriminator. Confirmed projects accumulate only
inside one homogeneous family, such as replacing `insufficient_structural_evidence` with a return-backed candidate.
Unrelated argument-count changes, output annotations, and contrasts without a preserved structural difference cannot
jointly satisfy the three-project threshold. A mixed family receives a stable derived policy ID and still requires an
independent holdout plus the normal regression gate.

Evaluation-only target clamps and ordinary Architect artifacts preserve a bounded, non-scoring candidate pool from the
available architecture source context. The pool prefers side-effect-free standalone returning contracts before
instance-bound candidates, but this ordering only chooses shadow trials: promotion still requires a measured positive
delta, executable acceptance, no role regression, three homogeneous training projects, and an independent holdout. If
both LLM routes time out, an executable-evidence failure class remains available to deterministic improvement plugins;
no diagnosis text or score credit is invented.

Historical matching projects may be reprobed to confirm the portable signature and are retained as regression evidence,
but only newly discovered matching projects enter holdout training. Replaying an old confirmation cannot satisfy the
independent-project gate or consume the bounded training budget.

For staged candidate-selection contrasts, structural discovery also requires a plausible recovery candidate in the same
project. The recovery target is retrieval evidence only and must pass the normal measured shadow gates. Admission keeps
the minimal sufficient structural discriminator; incidental typed-argument differences do not split a family when
return behavior or side-effect evidence already separates the failed and successful contracts.

Recovery discovery carries a ranked pool of at most four addressable module functions or direct class methods into the
shadow discriminator. Candidates require complete input-materialization evidence, value-producing return behavior, and
bounded runtime dependencies; nested callables and unresolved protocol/global-runtime boundaries are retrieval rejects.
Path location alone is not runtime evidence: the KB `cli_runtime_boundary` rule applies to explicit CLI entrypoints, not
to every pure helper or method stored below a `cli` package.

Promotion must reproduce the measured holdout treatment through the ordinary untargeted role route after the candidate
policy is applied. The reproduced minimum score, status, and executable acceptance signal must be at least as strong as
the shadow treatment before regression checks begin. Failure rolls the candidate policy back; a targeted shadow alone
is not production evidence.

An ordinary-route failure after target selection may indicate missing execution knowledge rather than a bad candidate.
Typed sample recipes belong in `executable_acceptance_policy.json`; pure-call exclusions belong in the declarative
side-effect policy; reusable source semantics belong in structural contract families backed by AST facts such as called
operations. These repairs still require an untargeted replay and an executable acceptance signal. They do not revive a
candidate-selection policy that failed reproduction.

Profile-effect evidence uses a same-source A/B trial. Target selection is held constant: the control evaluates the
exact source without an overlay, and treatment evaluates it with the temporary typed profile. Only the attributable
`treatment - control` delta may create a semantic contract profile candidate. A better alternate target is recorded as
target-selection experience and cannot be credited to the profile.

Run an attributable same-source effect trial:

```powershell
python tools\self_improvement_profile_effect.py --root . --project-dir PATH --source path/to/file.py:function --write
```

Run one training case:

```powershell
python tools\self_improvement_train.py --root . --project-dir PATH --target-score 9.7
```

Run the complete corpus loop. Hypothesis-driven discovery is enabled by default for writable runs:

```powershell
python tools\self_improving_foundation_trial.py --root . --projects-dir PATH --target-score 9.7
```

Use `--no-hypothesis-discovery` only to diagnose a fixed local corpus. `--no-write` also disables discovery because a
valid independent holdout requires a frozen selection and isolated checkout artifacts.

Use `--no-write` to skip the durable training report and KB candidate. Verified role evidence is still materialized
because the current evaluator checks both structured artifacts and generated human documents.

## Model Routing

- `local_l35`: default diagnostician. It handles classification and bounded hypothesis generation locally.
- `external_l45_intent_resolver`: `DeepSeek Chat`, used as a single-call teacher only when the local result is insufficient.
- Deterministic fallback: candidate trials continue when neither model is available.

This is a capability-sufficiency policy. A more expensive model is justified only by measured training wins on a
holdout corpus, not by a generally stronger model label.
## Retrieval-To-Role Target Alignment

Structural holdout screening now passes its highest-scoring source-backed callable
to the Foundation 1-3 pipeline through the existing evaluation-only target clamp.
The validation report records the requested target, the selected target, and their
alignment. This retrieval evidence selects what to measure; it is not promotion or
quality evidence and does not relax holdout admission.
Recovery metrics keep target-alignment rate separate from signature matching yield,
so search quality and role target drift cannot hide behind one aggregate number.

When a signature exhausts its initial search vocabulary, the policy can supply
additional architecture-family terms. Each term keeps an independent durable page
cursor, so a plan-version change opens genuinely new search windows instead of
repeating previously measured repositories.

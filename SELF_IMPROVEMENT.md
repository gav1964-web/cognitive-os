# Cognitive OS Self-Improvement

## Principle

A project that falls below the required role score is a training example. Cognitive OS diagnoses the failure,
changes only bounded role parameters, reruns the same unchanged evaluator, and records what the experiment proved.
The source project, score threshold, evaluator, role caps, and active knowledge base are not trainable parameters.

## Loop

1. Run the three foundation roles and take the minimum role score.
2. Ask the local L3.5 profile for a structured diagnosis.
3. Escalate once to the external teacher only when the local result fails, is uncertain, or is not actionable.
4. Test at most three source candidates already discovered by the deterministic analyzer.
5. Select the best attempt using measured role scores, never an LLM claim.
6. Stage the measured experience as a KB candidate and run post-training admission with the best confirmed challenger.
7. If the hypothesis is portable but evidence is still insufficient, build a `HypothesisValidationPlan` and ask the configured discovery capability for two or three unseen similar Python projects.
8. Train and verify sequentially on those independent holdouts. A later holdout may promote an allowlisted policy only after earlier projects supplied the configured repeated evidence.
9. Re-evaluate the original corpus. Roll back every changed promotion path when the corpus gate finds a regression or no attributable improvement.
10. When several target choices produce no gain, stop target search and propose a reusable semantic contract profile or a typed capability-development request.
11. Synthesize at most one temporary profile from AST evidence, evaluate it in an isolated context, and discard it after the trial.

The small hypothesis holdout and the large blind corpus have different jobs. The two-or-three-project holdout is an
active learning step selected from the portable failure class and structural signature. It answers whether one concrete
hypothesis generalizes. A 20-40 project multi-type blind corpus remains a release/calibration exam and must not be
reused as routine training evidence for every hypothesis.

Project discovery is a replaceable external capability. The current CLI adapter searches GitLab, freezes selection and
commit metadata under `artifacts/hypothesis_holdouts/<hypothesis_id>/`, and excludes every previously selected repository.
Provider timeout or rate limiting produces `HypothesisValidationTrial.status=blocked` with
`reason=external_discovery_failed`; it is not recorded as a failed technical hypothesis.

Temporary profiles cannot contain numeric score or ranking bonuses. They may only supply a typed contract family that
removes an unprofiled-target cap when source evidence proves every recognition gate. A successful profile is generalized
into a staged template and still requires independent cases and admission before it can enter active knowledge.
Raw `KnowledgeCandidate` records are never merged automatically. Separately registered improvement plugins may
auto-promote only their narrow allowlisted policy/config targets after repeated evidence, an independent holdout,
unchanged source projects, no role regression, and the normal corpus rollback gate.

Independent validation keeps recognition coverage separate from treatment evidence. A project that matches the AST
recognizer but already scores `9.7+` proves portability of the classifier only; it does not count toward the three
confirmed improvement cases required for review.

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

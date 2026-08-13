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
6. Stage the experience as a KB candidate. Active KB promotion remains a reviewed operation.
7. When several target choices produce no gain, stop target search and propose a reusable semantic contract profile.

Run one training case:

```powershell
python tools\self_improvement_train.py --root . --project-dir PATH --target-score 9.7
```

Use `--no-write` to skip the durable training report and KB candidate. Verified role evidence is still materialized
because the current evaluator checks both structured artifacts and generated human documents.

## Model Routing

- `local_l35`: default diagnostician. It handles classification and bounded hypothesis generation locally.
- `external_l45_intent_resolver`: `DeepSeek Chat`, used as a single-call teacher only when the local result is insufficient.
- Deterministic fallback: candidate trials continue when neither model is available.

This is a capability-sufficiency policy. A more expensive model is justified only by measured training wins on a
holdout corpus, not by a generally stronger model label.

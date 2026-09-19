# Three-Route Evaluation Protocol v2

This protocol tests product value rather than artifact volume.

Each frozen task is executed through three routes:

1. `direct_agent`: a real coding/workspace agent that receives no Cognitive OS artifacts.
2. `short_chain`: bounded intake, planning, implementation and verification without the complete role chain.
3. `full_chain`: the configured Project Analyzer through Reviewer chain.

All routes use the exact prompt digest and the same constraints. Route runners emit evidence receipts, never quality scores. A receipt records executor/model identity, time, cost, token usage, corrections, acceptance checks, artifacts, safety evidence and a route-neutral judge payload.

The direct route cannot use the legacy `deterministic_direct_baseline`; that implementation is a narrow proxy, not an agent comparison. Existing `metrics.json` verdicts are retained as historical diagnostics but have no v2 authority.

After all three receipts exist for a task, `bundle` replaces route identities with candidate IDs and strips executor/model labels. Candidate IDs use a fresh secret for every bundle and cannot be reconstructed from the public manifest. The blind evaluator scores requirement coverage, correctness, maintainability, evidence quality and safety. Unblinding and aggregation happen only after the independent scorecard is complete. Reports are grouped by task class; no global product claim is allowed with fewer than 20 complete tasks.

```bash
python tools/three_route_evaluation.py --root . freeze
python tools/three_route_evaluation.py --root . status
python tools/three_route_evaluation.py --root . readiness --output artifacts/evaluation_v2/input-readiness.json
python tools/three_route_evaluation.py --root . bundle
python tools/three_route_evaluation.py --root . score --bundle <bundle> --key <key> --scorecard <scorecard>
```

The blind key must not be given to the evaluator before the scorecard is final. The evaluator must not have produced any route output and declares both boundaries in the scorecard. Human corrections include any prompt clarification, retry guidance, manual patch or rubric-specific interpretation supplied after a route starts.

`readiness` checks whether the frozen task has executable inputs, independently of receipt coverage. A digest of a project name is not a digest of its source. Analysis, documentation and source-change tasks require `project_tree` inputs; prompt-only generation is allowed for CLI/service/negative tasks with explicit constraints and success criteria. Ablation workloads must be concretely frozen before execution.

Missing constraints, missing or changed source, redirected declarations, private files, symlinks and excessive inputs block readiness. The audit rejects `config.json`, `.env*`, `secret.key`, `.agents` and `.codex` before reading their contents, and does not modify the source or frozen manifest. Prepare a sanitized snapshot inside the workspace and freeze a new manifest when resolving input gaps; preserve earlier manifests and receipts as history.

The 2026-09-12 preparation is recorded in `prepared_inputs_20260912.json`.
Project analysis uses explicitly selected local source copies, with omissions
listed in the preparation record. Ablation `project_tree` declarations can include
one `supporting_input` object with a workspace-relative `path` and `tree_digest`;
readiness verifies that source as well as the concrete workload tree. Local
snapshots under `artifacts/evaluation_inputs/20260912` must be retained to reproduce
the campaign. Prior prompts/manifests remain in `history/inputs_before_20260912`.

Task15 has six predeclared external checks in `acceptance/check_uppercase_cli.py`.
The engineering run records the checker digest and preserves the failed initial
attempt. Passing these checks is not a direct/short/full comparison. Synthetic
image/workbook fixtures and existing source selections are declared as such and
must not be relabelled fresh holdout evidence.

`python tools/run_evaluation_routes.py` now runs real task15 adapters and writes
engineering drafts outside canonical receipts. `--model-route backup` pins the
configured backup for all routes; default `failover` retains normal routing.
Unknown billing/usage and mixed response models do not bypass v2 gates. Native
full-chain delivery is measured as it exists, including blocked greenfield output.
See `docs/architecture/route_trial_20260912.md` for scope, interventions and receipts.

The later native greenfield delivery stage is documented in
`docs/architecture/greenfield_delivery_20260912.md`. Task15 full now explicitly
uses `native_greenfield_bounded_delivery.v1`, including real specification binding,
bounded programmer execution and delivery review. This supported operation needs
no LLM call: its draft remains ineligible for the same-model v2 protocol. Do not
invent a model identity, invoke an otherwise unused model to populate telemetry,
or reinterpret older project-oriented runs as this new executor.

The CLI `status` reports `inputs_not_ready` and `bundle` refuses to write a blind bundle while input readiness is blocked. This input gate does not certify acceptance results or independent judging. Low-level APIs do not access live input trees, but now require an explicit `artifact_root` for result evidence. Archived receipts without the evidence described below remain historical records and cannot produce a new validated bundle/report.

## Evidence contract tightened on 2026-09-12

- Runtime, estimated cost and correction minutes must be finite, nonnegative numbers;
  booleans are invalid. Rubric scores, weights and winner margin are checked too.
  Estimated cost still needs an externally justified estimate: missing usage or
  zero tokens reported by a gateway must not be interpreted as free execution.
- Artifact paths are relative to `artifact_root` (the workspace root in the CLI).
  Bundle and score read their actual bytes and compare SHA-256. Missing files,
  duplicate paths, traversal, absolute paths, links/junctions and private config
  paths are rejected. Limits are 1,000 artifacts, 10 MB per file and 100 MB per receipt.
- `llm_attempts` contains raw telemetry records, including failed/skipped fallback
  attempts. `llm_trace` names a JSON artifact whose contents equal that list.
  A response record contains `requested_model`, `model`, `model_reported: true`
  and `provider_label`; failure/skip events use `attempt_failed`/`route_skipped`.
  The local inference sink emits these fields. Executors must attach the sink and
  persist its records; the evaluator does not fabricate missing historical traces.
- Every response model must equal the receipt's `model`, and all three receipts
  must declare the same model. A failed DeepSeek attempt followed solely by GigaChat
  responses can participate in a GigaChat comparison. Mixed successful generations
  are rejected for this same-model protocol, even if a runner relabels the final model.
- The withheld blind key binds the full manifest, policy digest and each receipt
  digest. Scoring requires those exact receipts and rechecks artifact bytes, so a
  cost/result edit after bundling invalidates the run. Status applies bundle checks,
  including duplicate receipts and model consistency, before granting eligibility.

These checks bind runner observations to files; they do not authenticate a runner
or prove that a gateway's model label identifies its actual backend. Hashes are
not signatures. Independent judging and verified acceptance execution remain
separate requirements. A source-copy test subprocess has the host process's
permissions and is not a security sandbox.

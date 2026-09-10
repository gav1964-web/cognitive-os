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
python tools/three_route_evaluation.py --root . bundle
python tools/three_route_evaluation.py --root . score --bundle <bundle> --key <key> --scorecard <scorecard>
```

The blind key must not be given to the evaluator before the scorecard is final. The evaluator must not have produced any route output and declares both boundaries in the scorecard. Human corrections include any prompt clarification, retry guidance, manual patch or rubric-specific interpretation supplied after a route starts.

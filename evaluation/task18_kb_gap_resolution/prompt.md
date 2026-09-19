# task18_kb_gap_resolution

## Prompt

Если KB не знает решения, попробуй решить через LLM и сформируй candidate или developer request.

## Success Criteria

- KB miss is recorded
- LLM output is not executed directly
- Next action is explicit

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Concrete KB-miss workload: propose a pure function normalizing RFC3339 timestamps to UTC while preserving fractional precision; fixture cases are supplied in workload.json.
- Record the actual KB lookup; if supported already, report that the miss assumption is false. No KB mutation, candidate promotion or direct execution of model text.
- Test KB resolution for the supplied timestamp normalization cases; generate candidate/developer request only. Candidate code is data and must not be executed or admitted.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task18_kb_gap_resolution

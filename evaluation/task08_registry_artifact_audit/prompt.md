# Prompt

## Original Prompt

Audit Cognitive OS registry separation and artifact/packet redundancy. Determine what should remain separate, what should become a derived view, and what should be merged or removed.

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Audit the frozen COS registry/*.json, config/role_directory.json and runtime schema/packet producers and consumers. Cite produced-but-unused field evidence and propose changes only.


- Allowed tools: static code/documentation analysis, registry validation tools, evaluation reports.
- Allowed network access: none.
- Allowed dependencies: existing repository dependencies only.
- Source mutation policy: no architectural code changes from this audit.

## Expected Inputs

- Registry files and plugin manifests.
- Runtime packet and role artifact definitions.
- Documentation describing registry and artifact responsibilities.

## Expected Outputs

- Source-of-truth map for Capability, Contract and Skill registries.
- Field-overlap map for `GoalSpec`, `IntentPacket`, `MotorPlanPacket`, Pipeline DSL and role artifacts.
- Keep/simplify/remove recommendations.
- Missing acceptance-test list.

## Success Criteria

- Distinguishes conceptual separation from duplicated storage.
- Identifies produced-but-unused fields.
- Does not collapse artifacts solely because names are similar.
- Produces an actionable simplification backlog.

## Known Ambiguities

- Some separation may be justified by authority boundaries rather than field uniqueness.


## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task08_registry_artifact_audit

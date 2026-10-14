# Prompt

## Original Prompt

Audit Cognitive OS registry separation and artifact/packet redundancy. Determine what should remain separate, what should become a derived view, and what should be merged or removed.

## Constraints

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


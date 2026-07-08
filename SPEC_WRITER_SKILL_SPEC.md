# SPEC_WRITER_SKILL_SPEC.md
**SpecWriterSkill v0.1**

SpecWriterSkill is a Level 4 role skill. It converts an ArchitectureDecisionRecord into an implementable TechnicalSpec with requirements, acceptance criteria, non-goals, traceability, and a bounded implementation handoff.

## Purpose

```text
ArchitectureDecisionRecord -> TechnicalSpec
```

The role exists to make architecture decisions actionable without allowing the architect to silently become the implementer.

## Inputs

```text
ArchitectureDecisionRecord
SpecWriterBrief
ChosenOption
TraceabilityTable
NonGoals
```

## Outputs

```text
TechnicalSpec
Requirements
AcceptanceCriteria
TraceabilityTable
ImplementationHandoff
```

## Forbidden Actions

SpecWriterSkill must not:

* edit source code;
* mutate `registry/capabilities.json`;
* execute pipelines;
* promote candidates;
* broaden the chosen architecture scope without returning a blocked artifact.

## Quality Checks

An acceptable TechnicalSpec must include:

* bounded scope;
* explicit requirements;
* acceptance criteria;
* preserved non-goals;
* traceability from ADR facts/decisions to acceptance checks;
* implementation handoff with expected next role.

## Output Shape

```json
{
  "artifact_type": "TechnicalSpec",
  "role": "spec_writer",
  "status": "ok",
  "scope": [],
  "requirements": [],
  "acceptance_criteria": [],
  "constraints": [],
  "non_goals": [],
  "traceability_table": [],
  "implementation_handoff": {
    "recommended_role": "implementer",
    "expected_output": "ImplementationPlan"
  },
  "forbidden_actions_observed": []
}
```

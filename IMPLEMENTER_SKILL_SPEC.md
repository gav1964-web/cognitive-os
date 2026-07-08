# IMPLEMENTER_SKILL_SPEC.md
**ImplementerSkill v0.1**

ImplementerSkill is a Level 4 role skill. It converts a TechnicalSpec into a bounded ImplementationPlan. It does not write code; it prepares the work package for a code-writing executor or human/Codex implementation turn.

## Purpose

```text
TechnicalSpec -> ImplementationPlan
```

## Inputs

```text
TechnicalSpec
Requirements
AcceptanceCriteria
TraceabilityTable
ImplementationHandoff
```

## Outputs

```text
ImplementationPlan
PatchScope
ExpectedFiles
VerificationCommands
RollbackPlan
AcceptanceMapping
```

## Forbidden Actions

ImplementerSkill must not:

* edit source code;
* mutate `registry/capabilities.json`;
* execute pipelines;
* promote candidates;
* widen scope beyond the TechnicalSpec.

## Quality Checks

An acceptable ImplementationPlan must include:

* bounded patch scope;
* expected files or directories;
* ordered implementation steps;
* verification commands;
* rollback plan;
* acceptance mapping;
* next role recommendation.

# ARCHITECT_SKILL_SPEC.md
**ArchitectSkill v0.2**

ArchitectSkill is a Level 4 role skill. It converts a project analysis artifact and a goal into an architecture decision artifact. It is not an executor, plugin, registry mutator, or code generator.

## Purpose

```text
ProjectMapReport + Goal + Constraints -> ArchitectureDecisionRecord
```

The role exists to keep architectural judgment explicit before Foundry or implementation work begins.

## Inputs

```text
ProjectMapReport
GoalStatement
Constraints
ExistingRuntimeDocs
```

Minimal MVP input may be a deterministic Project Analyzer report plus a goal string.

## Outputs

```text
ArchitectureDecisionRecord
SubsystemBoundaryMap
CapabilityModel
RiskList
NonGoals
OpenQuestions
TraceabilityTable
ArchitectureOptions
ChosenOption
RejectedOptions
SpecWriterBrief
```

The output must be a typed artifact, not free-form role dialogue.

## Forbidden Actions

ArchitectSkill must not:

* edit source code;
* write or promote plugins;
* mutate `registry/capabilities.json`;
* execute user pipelines;
* bypass Foundry admission;
* replace L3.5 planning or L2 validation.

## Quality Checks

An acceptable ArchitectureDecisionRecord must include:

* clear subsystem boundaries;
* proposed capability model;
* explicit risks;
* non-goals;
* open questions or a statement that none are known;
* traceability from project facts/tasks to architectural decisions;
* at least two architecture options;
* one explicit chosen option with reason/tradeoffs/prerequisites;
* rejected options with reasons;
* a bounded brief for SpecWriterSkill;
* next artifact recommendation.

## Output Shape

```json
{
  "artifact_type": "ArchitectureDecisionRecord",
  "role": "architect",
  "status": "ok",
  "goal": "...",
  "decision_summary": "...",
  "subsystem_boundaries": [],
  "capability_model": [],
  "risks": [],
  "non_goals": [],
  "open_questions": [],
  "traceability": [],
  "architecture_options": [],
  "chosen_option": {
    "id": "...",
    "reason": "...",
    "tradeoffs": [],
    "prerequisites": []
  },
  "rejected_options": [],
  "spec_writer_brief": {
    "scope": [],
    "files_or_symbols": [],
    "acceptance_targets": [],
    "constraints": []
  },
  "next_artifact": {
    "type": "TechnicalSpec",
    "recommended_role": "spec_writer"
  },
  "forbidden_actions_observed": []
}
```

## Training Tasks

1. Convert a simple CLI project report into subsystem boundaries and first extraction candidate.
2. Identify mixed-responsibility functions and propose capability extraction order.
3. Separate runtime execution concerns from L4 advisory interpretation.
4. Detect where a project needs process-boundary isolation before plugin promotion.
5. Produce non-goals that prevent accidental broad rewrites.
6. Map analysis tasks to traceable architecture decisions.
7. Explain why registry mutation belongs to Foundry promote, not ArchitectSkill.

# ARCHITECT_SKILL_SPEC.md
**ArchitectSkill v0.2**

ArchitectSkill is a Level 4 role skill. It converts a project analysis artifact and a goal into an architecture decision artifact. It is not an executor, plugin, registry mutator, or code generator.

## Purpose

```text
Existing project: ProjectMapReport + Goal + Constraints -> ArchitectureDecisionRecord
Greenfield product: UserPrompt + PromptAdequacy + Pattern/KB evidence -> ProductArchitectureRecord
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
ProductArchitectureRecord
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
Artifacts are APIs between roles, not reports for decoration. Downstream roles must consume explicit fields from the artifact instead of re-interpreting prose.

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
* for greenfield products: a `product_output_contract` that states the user-visible result shape;
* for greenfield products: `real_world_edge_cases` that capture likely failures and non-happy-path inputs before implementation starts;
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

## Greenfield Output Shape

```json
{
  "artifact_type": "ProductArchitectureRecord",
  "role": "architect",
  "status": "ok",
  "prompt": "...",
  "pattern_id": "...",
  "product_summary": "...",
  "architecture_style": "...",
  "product_output_contract": {
    "primary_output": "...",
    "user_visible_shape": "...",
    "constraints": []
  },
  "real_world_edge_cases": [
    {"id": "...", "description": "...", "success": "..."}
  ],
  "components": [],
  "main_scenarios": [],
  "interfaces": [],
  "data_model": [],
  "data_lifecycle": [],
  "external_boundaries": [],
  "research_hints": [],
  "architecture_options": [],
  "chosen_architecture_option": {},
  "risks": [],
  "open_questions": [],
  "spec_writer_brief": {
    "scope": [],
    "primary_contract": {},
    "acceptance_focus": [],
    "constraints": [],
    "product_output_contract": {},
    "real_world_edge_cases": []
  },
  "forbidden_actions_observed": []
}
```

For prompt-to-product tasks, Architect must catch product-level mismatches early: ordinary user input shape, expected output shape, external boundaries, likely real-world failures, and whether the request should stop for clarification. For example, a web research prompt must preserve "plain user query -> one summary + compact sources" and must list Cyrillic/IRI URL, noisy aggregator page and empty/malformed article handling before SpecWriter starts.

## Training Tasks

1. Convert a simple CLI project report into subsystem boundaries and first extraction candidate.
2. Identify mixed-responsibility functions and propose capability extraction order.
3. Separate runtime execution concerns from L4 advisory interpretation.
4. Detect where a project needs process-boundary isolation before plugin promotion.
5. Produce non-goals that prevent accidental broad rewrites.
6. Map analysis tasks to traceable architecture decisions.
7. Explain why registry mutation belongs to Foundry promote, not ArchitectSkill.

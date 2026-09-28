# SPEC_WRITER_SKILL_SPEC.md
**SpecWriterSkill v0.1**

SpecWriterSkill is a Level 4 role skill. It converts an ArchitectureDecisionRecord into an implementable TechnicalSpec with requirements, acceptance criteria, non-goals, traceability, and a bounded implementation handoff.

## Purpose

```text
Existing project: ArchitectureDecisionRecord -> TechnicalSpec
Greenfield product: ProductArchitectureRecord -> ProductTechnicalSpec
```

The role exists to make architecture decisions actionable without allowing the architect to silently become the implementer.

## Inputs

```text
ArchitectureDecisionRecord
ProductArchitectureRecord
SpecWriterBrief
ChosenOption
TraceabilityTable
NonGoals
```

## Outputs

```text
TechnicalSpec
ProductTechnicalSpec
Requirements
AcceptanceCriteria
TraceabilityTable
ImplementationHandoff
```

The artifact is an API between roles. SpecWriter must preserve machine-readable architecture decisions instead of replacing them with prose-only documentation.

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
* preserved `product_output_contract` when the input is a `ProductArchitectureRecord`;
* preserved `real_world_edge_cases` and matching verification strategy;
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

## Greenfield Output Shape

```json
{
  "artifact_type": "ProductTechnicalSpec",
  "role": "spec_writer",
  "status": "ok",
  "source_artifact": {},
  "scope": [],
  "requirements": [],
  "component_contracts": [],
  "primary_contract": {},
  "interfaces": [],
  "product_output_contract": {
    "primary_output": "...",
    "user_visible_shape": "...",
    "constraints": []
  },
  "real_world_edge_cases": [
    {"id": "...", "description": "...", "success": "..."}
  ],
  "data_model": [],
  "data_lifecycle": [],
  "error_model": [],
  "acceptance_criteria": [],
  "verification_strategy": {
    "contract_tests": [],
    "negative_tests": [],
    "integration_tests": [],
    "real_world_scenarios": [],
    "manual_review": []
  },
  "implementation_handoff": {
    "recommended_role": "implementer",
    "expected_output": "ImplementationPlan",
    "mode": "greenfield_project"
  },
  "forbidden_actions_observed": []
}
```

For prompt-to-product tasks, SpecWriter is responsible for converting product expectations into acceptance checks before implementation. If the user asked for one final summary, ordinary natural-language input, Cyrillic-safe URLs or compact source links, these requirements must appear in `acceptance_criteria` and `verification_strategy`; otherwise the handoff is too weak even if the structure of the TЗ looks complete.

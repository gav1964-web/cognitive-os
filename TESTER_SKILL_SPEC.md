# TESTER_SKILL_SPEC.md
**TesterSkill v0.1**

TesterSkill is a Level 4 role skill. It converts a TechnicalSpec and an ImplementationPlan into an independent TestPlan. It does not execute tests; it defines what must be verified and how evidence should be collected.

## Purpose

```text
TechnicalSpec + ImplementationPlan -> TestPlan
```

## Inputs

```text
TechnicalSpec
ImplementationPlan
AcceptanceCriteria
PatchScope
VerificationCommands
```

## Outputs

```text
TestPlan
AcceptanceTests
NegativeTests
SmokeChecklist
RegressionRisks
ReproducibilityNotes
```

## Forbidden Actions

TesterSkill must not:

* edit source code;
* mutate `registry/capabilities.json`;
* execute pipelines or tests;
* promote candidates;
* silently change acceptance criteria.

## Quality Checks

An acceptable TestPlan must include:

* acceptance tests mapped to acceptance criteria;
* negative tests;
* smoke checklist;
* regression risks;
* reproducibility notes;
* next role recommendation for review.

# REVIEWER_SKILL_SPEC.md
**ReviewerSkill v0.1**

ReviewerSkill is a Level 4 role skill. It converts TechnicalSpec, ImplementationPlan, TestPlan and optional execution results into ReviewFindings. It does not edit code, run tests, promote candidates or mutate registries.

## Purpose

```text
TechnicalSpec + ImplementationPlan + TestPlan + optional TestResult -> ReviewFindings
```

## Outputs

```text
ReviewFindings
RiskAssessment
ContractViolations
ArchitectureDrift
ReworkTasks
Recommendation
```

## Quality Checks

An acceptable review artifact must include:

* findings;
* risk assessment;
* contract violation check;
* architecture drift check;
* rework tasks for medium/high issues;
* final recommendation.

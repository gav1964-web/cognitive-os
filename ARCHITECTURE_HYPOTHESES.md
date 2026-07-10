# Architecture Hypotheses

This document tracks architectural claims that must be proven, simplified or removed.

The project should not keep architectural complexity only because it is elegant. A component, layer, registry or artifact earns its place by improving reliability, auditability, reproducibility, safety or review cost for supported task classes.

## Decision Rule

For every disputed element:

```text
keep it if evidence shows value;
simplify it if it duplicates another mechanism;
remove or demote it if it does not survive evaluation.
```

No result produced by Cognitive OS itself is ground truth. Evaluation requires external checks, reproducible artifacts, teacher/corrector review or explicit human architectural decision.

## H1: Role Separation

Claim:

```text
Project Analyzer -> Architect -> SpecWriter -> Implementer -> Tester -> Reviewer
```

produces better outcomes than a smaller role chain.

Risk:

The chain may add latency and artifacts without improving quality. Some task classes may work better with merged roles, for example `Architect+SpecWriter` or `Tester+Reviewer`.

Evaluation:

- compare full role pipeline against merged-role baselines;
- measure missed requirements, artifact completeness, repair cycles and review blockers;
- run on project-analysis, CLI utility and FastAPI tasks.

Decision criteria:

- keep full separation only where it improves measurable outcomes;
- allow task-class-specific merged routes if they perform as well with less overhead.

## H2: Registry Separation

Claim:

```text
Capability Registry
Contract Registry
Skill Registry
```

represent distinct system interfaces.

Risk:

The registries may duplicate facts and create synchronization overhead.

Evaluation:

- identify source-of-truth fields;
- prove which views are derived;
- add tests that detect registry drift;
- check whether Skill Registry has executable use, not only documentation value.

Decision criteria:

- keep conceptual separation if it maps to distinct questions:
  - what can run?
  - under what contract can it run?
  - which role transforms artifact A into artifact B?
- generate derived views where possible;
- remove or demote any registry that has no runtime, validation or evaluation role.

## H3: Artifact / Packet Redundancy

Claim:

`GoalSpec`, `IntentPacket`, `MotorPlanPacket`, Pipeline DSL and role artifacts are separate APIs between layers.

Risk:

Some artifacts may copy the same fields and become wrappers rather than interfaces.

Evaluation:

- compare field overlap;
- check which fields are consumed by the next layer;
- detect fields that are produced but never used;
- verify traceability from prompt to execution/review.

Decision criteria:

- keep an artifact if it changes authority, audience or allowed actions;
- merge artifacts that only rename the same data;
- require every layer API to document producer, consumer, authority and forbidden actions.

## H4: Strict Layering vs Controlled Bypass

Claim:

Strict routing through L4, L3.5, L2 and L1 improves safety and inspectability.

Risk:

Strict layering may slow experimentation or add unnecessary handoffs for simple tasks.

Evaluation:

- compare strict route against explicit bypass scenarios;
- bypass must be declared, logged and validated;
- measure result quality, speed, source safety and artifact completeness.

Decision criteria:

- keep strict route as the default safety path;
- allow experimental bypass only as an evaluation scenario, not as an implicit shortcut;
- promote a bypass route only if it preserves source safety and traceability.

## H5: Stage 3 Product Slice

Claim:

Stage 3 adds useful product-level verification over Stage 2 verified packages.

Risk:

Stage 3 may be a documentation wrapper that does not reduce review cost.

Evaluation:

- compare Stage 2 package review against Stage 3 product-slice review;
- measure human correction time, missed scenarios, documentation drift and release confidence.

Decision criteria:

- keep Stage 3 where it reduces review effort or catches errors Stage 2 misses;
- demote it to optional reporting where it adds no measurable value.

## H6: Memory Separation

Claim:

Memory Index, Dialogue Context and Knowledge Gap artifacts represent distinct forms of experience.

Risk:

Separate memory mechanisms may be replaced by one evidence store with typed tags.

Evaluation:

- measure which mechanism contributes evidence to decisions;
- track duplicate storage;
- compare unified tagged memory against separated memory APIs.

Decision criteria:

- keep separation only where retrieval, authority or lifecycle differs materially;
- otherwise collapse into a simpler evidence store with typed views.

## H7: Foundry Dependency Bundling

Claim:

Foundry blocks local-module dependencies to preserve safety in MVP.

Risk:

This is too conservative for real project extraction and blocks useful candidates.

Evaluation:

- add a controlled dependency-bundling design;
- run on previously blocked local-module cases;
- compare safety findings, contract-test quality and extraction usefulness.

Decision criteria:

- keep block-only behavior for unsafe or unresolved dependencies;
- support explicit local-module bundling when dependencies are bounded, copied into sandbox and tested.

## H8: Semantic Debug Loop

Claim:

Current deterministic repair loops are safer and sufficient for MVP.

Risk:

They cannot repair semantic logic drift and may make the programmer role look weaker than it needs to be.

Evaluation:

- introduce sandbox-only LLM rework for semantic failures;
- require `FailureAnalysis -> bounded ReworkPlan -> PatchPackage -> tests -> Reviewer`;
- compare against deterministic-only repair.

Decision criteria:

- never allow open-ended repair;
- promote semantic repair only if it improves test outcomes without increasing drift or source safety violations.

## Near-Term Action

The next evidence track is:

1. Run the first 6 evaluation tasks.
2. Add architecture hypothesis tasks for roles, registries, artifacts, Stage 3 and bypass.
3. Produce comparison reports before adding new architectural layers.


# Cognitive OS Positioning

## Short Version

Cognitive OS is not trying to become a better chat UI, a workspace assistant, or a generic autonomous coding agent.

The project is positioned as a **contract-driven intent-to-engineering pipeline and verification harness for LLM-assisted software work**.

Its job is to turn a human goal into explicit, versioned, inspectable engineering interfaces:

```text
prompt
-> adequacy gate
-> GoalSpec / contracts
-> role artifact APIs
-> bounded implementation or analysis package
-> tests / review / verification report
-> human release decision
```

The LLM remains useful, but it is not the system boundary. The boundary is the artifact contract.

## Why This Still Matters

Workspace agents, coding agents and integrated AI IDEs can already read files, edit code, run commands and help with project tasks. Cognitive OS should not compete with them on that surface.

The durable value of Cognitive OS is different:

- make the path from intent to implementation explicit;
- separate facts, judgments, plans, patches, tests and review findings;
- keep generated work portable outside a single chat transcript or provider UI;
- make runs reproducible enough to compare, audit and rerun;
- make source modification a controlled release decision, not an implicit side effect;
- support multiple LLM providers and executors behind the same contracts;
- measure whether a mediated route actually beats a direct agent run.

In other words, Cognitive OS is useful only if it improves reliability, auditability or repeatability for bounded task classes.

## What Cognitive OS Is Not

Cognitive OS is not:

- a replacement for ChatGPT Work, Codex, Copilot, Cursor, IDEs or local LLM frontends;
- a universal desktop assistant;
- a one-button arbitrary software engineer;
- a generic website or app generator;
- a self-learning system that treats its own output as truth;
- an agent chatroom where roles negotiate through prose;
- a system that should gain power by giving an LLM broader direct access.

If an ordinary direct-agent loop solves a task faster, with equal quality, equal traceability and lower operational cost, Cognitive OS should not wrap that task.

## Current Differentiators

The repository currently focuses on mechanisms that ordinary chat-style agent loops do not make first-class:

- `PromptAdequacyGate` / `GoalSpec` style intake before execution;
- typed role artifacts for Architect, SpecWriter, Implementer, Tester and Reviewer;
- layer separation between L4 semantic judgment, L3.5 route planning, runtime execution and L1 capabilities;
- sandbox package generation before source changes;
- project-change scenarios with fixture-only application and source immutability checks;
- builder registry for allowlisted implementation mechanisms;
- `teacher_reference != ground_truth` as a protected curriculum invariant;
- acceptance probes that validate behavior as artifacts rather than conversation quality.

These are not proof of broad autonomy. They are proof points for a narrower claim: bounded LLM-assisted work can be lowered into explicit artifact APIs with stronger control boundaries.

## Artifacts Are APIs

The most important design point is that Cognitive OS artifacts are not passive documents.

They are interfaces between layers:

```text
GoalSpec
-> ArchitectureDecisionRecord
-> TechnicalSpec
-> ImplementationPlan
-> TestPlan
-> ReviewFindings
```

Each artifact is a contract for the next step. It defines allowed assumptions, preserved constraints, evidence links, scope boundaries, forbidden actions and verification expectations.

This is why prose conversation between roles is not enough. A role may produce a human-readable explanation, but the next role consumes the typed artifact API.

## Product Shape

The near-term product shape is:

```text
Cognitive OS = intent pipeline + verifier + release harness
```

It can sit in front of different executors:

- a local model;
- a cloud model;
- Codex-like implementation tooling;
- a future workspace agent;
- deterministic local tools.

The same prompt should produce comparable contracts, plans, reports and verification results regardless of which executor implements the bounded work.

## Evaluation Requirement

Cognitive OS should be judged against direct agent usage, not against an imaginary manual baseline.

For each supported task class, the question is:

```text
Does Cognitive OS -> same executor produce better checked outcomes
than direct prompt -> same executor?
```

Better means fewer missed requirements, clearer artifacts, safer source boundaries, more reproducible runs, fewer uncontrolled repair loops, or lower review cost.

If that cannot be shown for a task class, that task class should remain out of scope.

See `EVALUATION_PLAN.md` for the measurement plan.

The same rule applies internally: roles, registries, layer boundaries, memory mechanisms and product stages are hypotheses until measured. See `ARCHITECTURE_HYPOTHESES.md`.

# External Research Loop Spec

## Problem

When a human lacks information, they can search external sources before answering. Cognitive OS must do the same without turning L4 into an unconstrained browser or allowing unsupported facts into the KB.

## Contract

The loop is explicit:

```text
missing fact
-> KnowledgeGapPacket
-> ResearchPlan
-> bounded acquisition capability
-> SourceDigest
-> role decision
-> optional KB candidate
```

L4 may identify the gap and interpret evidence, but it does not browse freely. L1 capabilities perform concrete acquisition actions under source policy.

## Artifacts

`KnowledgeGapPacket`:

- `gap_id`
- `question`
- `needed_for`
- `role`
- `reason`
- `acceptable_sources`
- `confidence_required`
- `decision_if_unresolved`

`ResearchPlan`:

- bounded steps;
- source type;
- query or URL requirement;
- purpose;
- `execute_by_default`.

`SourceDigest`:

- source type;
- extracted facts;
- confidence;
- evidence hash;
- limitations.

## Source Policy

Supported source classes:

- `official_docs_fetch`: allowlisted official documentation excerpts.
- `github_repository_search`: comparable project discovery, implementation pattern inspiration, edge-case discovery.
- `user_clarification`: human-provided missing requirements or domain facts.
- local project evidence and installed package probes from existing Knowledge Gap Loop.

External sources are evidence, not truth. GitHub results must never be used to copy code verbatim and never override official docs or local contract tests.

## Trigger Policy

Project analysis creates a research gap when architecture synthesis is generic or weak, for example:

```text
matched_rule = python_project
or confidence = low
```

The default action is to return a plan, not perform network access automatically.

Implemented contract:

- `runtime/research_loop.py`
- `runtime/knowledge.py`
- `runtime/knowledge_source_policy.py`

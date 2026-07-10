# Evaluation Plan

## Purpose

This plan defines how to test whether Cognitive OS adds real value over direct LLM-agent usage.

The project must not assume that more architecture automatically means better results. Every supported class should be compared against a direct baseline that uses the same executor or model family whenever possible.

## Main Question

```text
For bounded software tasks, does the Cognitive OS route produce more reliable,
auditable and reproducible outcomes than a direct agent route?
```

## Compared Routes

### Route A: Direct Agent Baseline

```text
user prompt
-> direct executor / coding agent / workspace agent
-> result
```

The direct route may use the same underlying LLM or executor available to Cognitive OS. It should be given the same task prompt and the same allowed tool boundaries where possible.

### Route B: Cognitive OS Mediated Route

```text
user prompt
-> Prompt Adequacy Gate
-> GoalSpec / contracts
-> role pipeline
-> sandbox implementation or analysis package
-> tests / review / verification report
-> release decision
```

The mediated route must record artifacts and cannot silently mutate the source project unless the scenario explicitly permits it.

For evaluation purposes, these artifacts are treated as APIs between steps, not as optional explanatory reports. A run is incomplete if a later step relies on information that was not present in the preceding artifact contract.

## Initial Corpus

Use 20-30 bounded tasks before making broad claims.

Recommended groups:

- CLI utilities and file-processing tools;
- small FastAPI/local-service packages;
- project analysis and improvement-planning tasks;
- sandbox project-change tasks on fixture copies;
- documentation/specification tasks with measurable completeness;
- negative tasks where the correct result is clarification or controlled refusal.

Each task should include:

- prompt;
- allowed dependencies and network policy;
- expected inputs and outputs;
- acceptance checks;
- source mutation policy;
- scoring rubric;
- known ambiguity notes.

## Metrics

Measure at least:

- requirement coverage;
- missed or invented requirements;
- test pass rate;
- verification pass rate;
- number of repair cycles;
- uncontrolled retry or drift count;
- reproducibility across repeated runs;
- time and approximate model/tool cost;
- artifact completeness;
- source safety violations;
- reviewer-blocking findings;
- human correction effort.

Use separate scoring for facts and judgments:

```text
facts -> checked against evidence
judgments -> scored by rubric
teacher_reference -> review target, not ground truth
```

## Success Criteria

A task class can be considered supported when the Cognitive OS route shows:

- no source safety violations under the declared policy;
- stable artifact production across repeated runs;
- verification reports that explain pass, fail or controlled block;
- fewer missed requirements or fewer repair cycles than the direct route;
- no automatic code correction based only on the system's own unverified output.

A controlled `blocked`, `needs_clarification` or `needs_rework` result is valid when the evidence supports it.

## Rules

- Use the same original prompt for both routes.
- Do not improve one route's prompt unless the same improvement is available to the other route.
- Record all manual teacher/corrector interventions.
- Do not treat a teacher reference as ground truth.
- Do not let the system modify its own source code from its own evaluation output.
- Keep generated artifacts versioned or reproducibly named.
- Preserve source-project immutability unless the scenario explicitly authorizes changes.

## Reporting Format

Each evaluation run should produce a compact report:

```text
task_id
route
executor/model
prompt_hash
input_artifacts
output_artifacts
acceptance_result
test_result
review_result
repair_cycles
source_mutation_detected
human_corrections
score_summary
known_limits
```

The final comparison should group results by task class rather than averaging unrelated tasks into one misleading number.

## Near-Term Next Step

Create a small evaluation harness for 5-8 existing tasks first:

- one project-analysis task;
- one sandbox project-change task;
- one CLI utility generation task;
- one FastAPI package generation task;
- one negative or clarification task.

Only after the report format is stable should the corpus expand to 20-30 tasks.

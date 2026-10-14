# Role Questionnaire Field Trial

## Purpose

`RoleQuestionnaireReport` is a diagnostic artifact for checking whether Cognitive OS roles can answer practical project-analysis questions from bounded evidence.

It is not a replacement for role API artifacts:

```text
ProjectMapReport
-> ArchitectureDecisionRecord
-> TechnicalSpec
-> ImplementationPlan
-> TestPlan
-> ReviewFindings
```

The questionnaire sits beside those artifacts and asks each role the same kind of questions a human reviewer would ask during a field trial.

## Role Coverage

Each project receives 12 evidence-bound questions for each current role:

- `project_analyzer`
- `architect`
- `spec_writer`
- `implementer`
- `tester`
- `reviewer`
- `researcher`

This produces 84 question/answer rows per project.

## Evidence Policy

Answers must be derived from local analyzer evidence:

- `ProjectMapReport`
- `extract_python_structure`
- `extract_runtime_commands`
- L3.5 project signals
- L4 project interpretation
- architecture synthesis
- research gap and research plan

If evidence is missing, the answer must mark a gap instead of inventing a fact.

## Non-Goals

- Do not treat questionnaire answers as ground truth.
- Do not mutate source projects.
- Do not auto-admit KB records from one project.
- Do not use role questionnaires as source-code edit instructions.
- Do not replace role API artifacts with prose answers.

## GitHub 20 Trial

`tools/github_role_questionnaire_probe.py` runs:

```text
GitHub repo
-> Project Analyzer
-> L3.5/L4 interpretation
-> RoleQuestionnaireReport
-> Role Pipeline excerpt
-> aggregate JSON/Markdown report
```

The expected output is written under:

```text
artifacts/github_role_questionnaire_20c/
```

The trial records:

- number of successfully analyzed projects;
- total role questions answered;
- evidence gaps;
- matched architecture rules;
- role pipeline recommendations;
- safety invariants.

## Quality Use

The report is useful when comparing role maturity:

- high gap count means analyzer evidence is still too weak;
- generic answers mean KB/rule coverage is too shallow;
- repeated gaps can become KB candidates only after multiple confirmations and human/Codex approval;
- failed projects should improve analyzer robustness before new roles are added.

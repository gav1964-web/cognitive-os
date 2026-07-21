# Local Automation MVP

## Target

The near-term MVP target is:

```text
Prompt -> Verified Local Automation Package
```

This is not a claim that Cognitive OS can build arbitrary software. It is a
bounded product slice for locally verifiable automation work.

## In Scope

- Python CLI tools.
- Local small services without GUI.
- File, document, image, text, archive, table and structured-data automation.
- OCR/vision-backed workflows when default tests use fixtures or injectable text.
- Web/API clients and scraping when required tests use fixtures or mocks; live
  network may only be optional smoke evidence.
- Project analysis and improvement planning.
- Sandbox-only implementation packages with README, tests, verification report
  and review/release decision.

## Out Of Scope For This MVP

- GUI applications.
- SQL databases as required runtime state.
- Production deployment.
- Long-running production services.
- Direct mutation of the user's source project without explicit approval.
- Uncontrolled dependency installation.
- Live network as mandatory acceptance evidence.
- Free execution of LLM-generated code.

## Acceptance Shape

A supported prompt should produce one of:

- `release_ready` or `release_ready_with_risks` verified sandbox package;
- `slice_ready` product-slice wrapper over a verified package;
- controlled `blocked` / clarification output with a clear reason.

The MVP is credible only when the same acceptance command repeatedly passes on
a mixed corpus of supported and intentionally unsupported prompts.

## Configuration-First Rule

At L4/L4.5, supporting a new task should not usually require Python-code
changes. The runtime should interpret external records:

- role definitions in `config/role_directory.json`;
- prompt intake and boundary markers in `config/prompt_intake_rules.json`;
- prompt-to-Stage-2-template routing in `config/stage2_template_routes.json`;
- L4 prompt-to-product transition and escalation reason rules in `config/l4_decision_rules.json`;
- L4.5 existing-means/developer-request mappings in `config/semantic_resolution_rules.json`;
- OperationRecipe contracts, transform markers, transform expressions and L4.5 recipe prompt rules in `config/operation_recipe_rules.json`;
- sandbox programmer profile policy, parser shape, graph family and admission shape in `config/sandbox_programmer_profiles.json`;
- sandbox release/admission/evaluation policy in `config/sandbox_release_policy.json`;
- interface contracts in `registry/interface_contracts.json`;
- operation recipes and operation registries;
- sandbox attempt policy in `registry/sandbox_attempt_policy.json`;
- curricula and KB records.

The active policy is `config/runtime_interpreter_policy.json`. Its target is
that roughly 90 percent of new L4/L4.5 task support is added through
configuration, registries, recipes, curricula or KB records. Code changes are
reserved for reusable interpreter primitives, validators, safe adapter
boundaries, bug fixes and test harness improvements.

The configuration-first rule is guarded by four diagnostic artifacts:

- `ConfigDoctorReport` from `tools/config_doctor.py` validates loaders and
  cross-catalog references between role directory, Stage 2 routes, L4/L4.5
  rules, operation recipes, interface contracts, sandbox operations and attempt
  policy.
- `ConfigCoverageReport` from `tools/config_coverage.py` is advisory evidence
  for which templates, rules, transforms and profiles are exercised by tests or
  trial registries.
- `RuleTrace` is embedded into every `VerifiedSystemPackage` and records which
  external config/rule sources participated in the decision.
- `ConfigMutationSandboxReport` from `tools/config_mutation_sandbox.py` validates
  a proposed JSON config replacement without modifying the active target file.

## Current Trial

The current registry-driven trial is:

```powershell
python tools\local_automation_mvp_trial.py --root . --write
```

Cases are declared in:

```text
registry/local_automation_mvp_cases.json
```

The current corpus checks:

- Stage 2 CLI package generation;
- Stage 2 image/document automation package generation;
- Stage 2 local FastAPI service generation;
- sandbox programmer operation composition;
- sandbox atomic operations with L4.5 prompt normalization, including file-transform, `argv -> stdout`, `argv -> file`, `stdin -> stdout`, `stdin -> file` and `file -> stdout` CLI shapes;
- interface contracts from `registry/interface_contracts.json`, currently including `argv_stdout_numeric_expression`, `argv_to_file_numeric_expression`, `stdin_to_stdout_text_transform`, `stdin_to_file_text_transform`, `file_to_stdout_text_transform` and `file_to_file_text_transform`;
- `OperationRecipe` artifacts that bind interface contract, transform, expression and evidence before code generation, including deterministic recipe parsing when the prompt cleanly specifies input channel, output channel and transform;
- `GeneratedPackageEvaluation` artifacts that score prompt presence, selected operation evidence, interface contract, recipe/contract match, operation graph, tests, README, sandbox verification, admission and no-mutation invariants;
- bounded L4.5 OperationRecipe fallback after deterministic and operation-id normalization no-match;
- controlled refusal for GUI, SQL DB, production deploy, autonomous source edits and mandatory live-network acceptance;
- `needs_clarification` routing for bounded but underspecified prompts, with explicit clarification questions.

Latest local smoke result: `39/39 passed`, pass rate `1.0`.

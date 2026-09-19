# task19_role_directory_extension

## Prompt

Добавь новую роль через справочник ролей без изменения runtime-кода.

## Success Criteria

- Role is data-defined
- Gates are contract-based
- No role-specific facade added

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- Add a data-defined role named evaluation_evidence_reviewer to a copy of config/role_directory.json, using an existing compatible handler.
- Require evidence references, emit a review artifact, and validate directory/contracts. Runtime/plugins/knowledge changes are forbidden; unsupported handler reuse must be reported as a block.
- Extend only role configuration in a copy of the frozen COS source, as specified in the task constraints.

## Frozen Input Location

artifacts/evaluation_inputs/20260912/workloads/task19_role_directory_extension

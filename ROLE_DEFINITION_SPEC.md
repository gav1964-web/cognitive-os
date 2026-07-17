# Role Definition Runtime

## Principle

Cognitive OS runtime code is a role definition interpreter.

Roles are not hard-coded personas in Python. A role is an external JSON definition
that declares:

- role id and order;
- consumed artifacts;
- produced artifacts;
- KB filters;
- policy constraints;
- questionnaire items;
- answer providers.

Adding a role such as `sql_architect` must not require a code change when the
role can be expressed through existing providers, contracts, and policies.

## Runtime Boundary

The runtime may contain:

- role definition loader;
- schema validation;
- answer provider interpreter;
- contract validation;
- deterministic transition rules;
- KB matching;
- LLM adapter as bounded hypothesis source;
- artifact writer;
- test/evaluation harness.

The runtime should not contain:

- fixed role list as product logic;
- role-specific questionnaire sections;
- role admission by Python module creation;
- implicit LLM authority.

## Files

- `roles/*.json` contains role definitions.
- `config/role_record_defaults.json` maps KB record types to role ids.
- `runtime/role_definitions.py` loads role definitions.
- `runtime/role_questionnaire_sections.py` interprets role question schemas.
- `runtime/role_knowledge.py` reads role ids and KB defaults from external config.

## RoleDefinition v1

Required fields:

- `schema_version`: must be `role_definition.v1`;
- `role_id`;
- `label`;
- `order`;
- `consumes`;
- `produces`;
- `kb_filters`;
- `policy`;
- `questions`.

Each question declares:

- `id`;
- `question`;
- `answer`;
- `evidence`;
- optional `confidence`.

The `answer` object is interpreted by provider type. Current providers:

- `ctx`: read a value from Project Analyzer context by path;
- `helper`: call a deterministic answer helper;
- `constant`: return literal text/value;
- `target`: return selected first capability;
- `first`: return first non-empty provider result;
- `object`: compose an object from child providers.

## Admission Policy

New roles should be added as JSON first. Runtime code changes are allowed only
when a new role needs a genuinely new generic provider or contract mechanism.

That provider must be role-neutral. For example, adding a generic `sql_schema`
answer provider is acceptable; adding `run_sql_architect()` as a hard-coded
role path is not.

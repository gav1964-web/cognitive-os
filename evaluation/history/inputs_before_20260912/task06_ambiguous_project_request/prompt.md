# Prompt

## Original Prompt

Сделай нормальный проект для работы с данными.

## Constraints

- Allowed tools: prompt analysis and clarification only unless sufficient requirements are provided.
- Allowed network access: none.
- Allowed dependencies: none before clarification.
- Source mutation policy: no generated package or source edits before clarification.

## Expected Inputs

- Ambiguous user prompt without clear system type, inputs, outputs or success criteria.

## Expected Outputs

- Clarification questions or a controlled `needs_clarification` result.
- No implementation package unless the route invents assumptions, which should be counted against it.

## Success Criteria

- Does not hallucinate a full product specification.
- Identifies missing inputs, outputs, constraints and acceptance criteria.
- Produces concise clarification questions.
- Avoids source changes.

## Known Ambiguities

- A direct agent may choose to assume a common data project shape; this should be scored as invented requirements unless explicitly framed as assumptions.


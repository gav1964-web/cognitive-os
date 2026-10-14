# task20_prompt_adequacy_gate

## Prompt

Сделай что-нибудь полезное с моим проектом.

## Success Criteria

- ClarificationPacket or controlled block
- No invented requirements
- No implementation attempt without adequacy

## Constraints

- Use Python 3.10+; generation and verification run in a fresh output directory, with no changes to frozen inputs.
- No network from produced programs or tests. Model inference may use the configured local gateway only; record every model attempt.
- No package installation during a route. Use the frozen available dependencies; report missing optional adapters explicitly.
- Per route budget: 20 model calls, 120000 reported total tokens, 900 seconds; record unknown usage as unknown, never invent zero cost.
- All routes receive these same constraints and input bytes. Log every clarification, manual edit and retry; none are supplied silently.
- This is intentionally under-specified. Return clarification questions or a controlled block; no project path or desired change is supplied and none may be invented.

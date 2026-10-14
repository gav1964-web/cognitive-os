# Prompt

## Original Prompt

Напиши CLI-конвертер файлов `.md` в `.rtf`.

## Constraints

- Allowed tools: local file generation, local tests, no source mutation outside generated package.
- Allowed network access: none.
- Allowed dependencies: Python standard library preferred; external dependencies must be justified.
- Source mutation policy: generated package or sandbox only.

## Expected Inputs

- CLI arguments: input Markdown path and output RTF path.
- Markdown text file encoded as UTF-8.

## Expected Outputs

- RTF file preserving plain text, headings, paragraphs and basic emphasis where supported.
- README with usage.
- Tests for basic conversion and invalid input.

## Success Criteria

- Provides a runnable CLI.
- Handles missing input file with a clear error.
- Produces valid RTF header/body structure.
- Includes tests and run instructions.

## Known Ambiguities

- Full Markdown semantics are not required unless explicitly implemented.


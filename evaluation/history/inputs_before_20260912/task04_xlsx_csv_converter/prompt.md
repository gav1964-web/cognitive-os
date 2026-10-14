# Prompt

## Original Prompt

Напиши CLI-конвертер `.xls/.xlsx` в `.csv` и обратно.

## Constraints

- Allowed tools: local file generation, local tests, no source mutation outside generated package.
- Allowed network access: none.
- Allowed dependencies: external spreadsheet libraries are allowed only if declared and tested; legacy `.xls` support may be explicitly limited if dependency risk is high.
- Source mutation policy: generated package or sandbox only.

## Expected Inputs

- CLI arguments specifying mode, input path and output path.
- Spreadsheet or CSV files.

## Expected Outputs

- CSV file from spreadsheet input.
- Spreadsheet file from CSV input.
- README with dependency and limitation notes.
- Tests for `.xlsx` and CSV round-trip where supported.

## Success Criteria

- Distinguishes `.xlsx` from legacy `.xls` support.
- Handles missing files and unsupported extensions cleanly.
- Does not silently drop rows or columns in simple fixtures.
- Includes tests and run instructions.

## Known Ambiguities

- Full `.xls` support may require optional dependencies and should be treated explicitly.


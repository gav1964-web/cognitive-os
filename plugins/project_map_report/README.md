# Project map report

Owns the source-backed project map and source-health interpretation.
`knowledge/source_health.json` declares bounded repository-root test-data
prefixes. Syntax errors there are reported as test-data noise, never silently
discarded or treated as proof of executable health. Unknown paths and executable
tests retain the damaged-source classification. Consumer: Project Analyzer.

Implementation: `src/source_health.py`, `src/syntax_context.py`.
Verification: `tests/test_syntax_context.py` and the plugin test suite.
Contract version: plugin 0.2.0; existing source-health fields retained, separate
test-data counts and authority added. No project-name-specific exceptions.

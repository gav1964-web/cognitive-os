# Promoted Evidence

This directory contains durable evidence used by current maturity, promotion, or architecture claims.

- `artifacts/` stores immutable content-addressed copies of evidence reports.
- `ledger/` stores canonical entries binding each report to its SHA-256, producer, independent evaluator, and replay command.
- Disposable test output remains under ignored `artifacts/` and cannot by itself authorize promotion.

Use `python tools/evidence_ledger.py --root . promote ...` to promote a report and `verify` to recheck its digest and provenance. Committing both generated files is required before documentation may cite the evidence as current authority.

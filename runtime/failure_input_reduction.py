"""Budgeted fixture reduction with repeated failure signatures in source snapshots."""
from __future__ import annotations

import json
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from .source_refactor_analysis import digest
from .stage_finalization_workspace import inventory, snapshot, owned_path, changed_files
from .stage_finalization_verification import verify_snapshot


def minimize_bytes(value: bytes, reproduces, *, max_attempts: int = 24) -> tuple[bytes, int]:
    """Delete contiguous partitions; the caller owns the failure oracle and baseline."""
    if max_attempts < 1:
        raise ValueError('positive_attempt_budget_required')
    attempts, partitions = 0, 2
    while value and attempts < max_attempts:
        width = max(1, (len(value) + partitions - 1) // partitions)
        reduced = False
        for start in range(0, len(value), width):
            candidate = value[:start] + value[start + width:]
            attempts += 1
            if reproduces(candidate):
                value, partitions, reduced = candidate, max(2, partitions - 1), True
                break
            if attempts >= max_attempts:
                break
        if not reduced:
            if partitions >= len(value):
                break
            partitions = min(len(value), partitions * 2)
    return value, attempts


def reduce_failure_fixture(root: Path, *, fixture: str, tests: list[str], max_attempts: int = 24,
                           timeout: int = 30, pytest_plugins: list[str] | None = None) -> dict:
    root = root.resolve()
    source = owned_path(root, fixture)
    if source.suffix.lower() not in {'.txt', '.json', '.csv', '.bin', '.xml', '.yaml', '.yml'}:
        raise ValueError('explicit_data_fixture_required')
    before = inventory(root)
    if fixture not in before:
        raise ValueError('fixture_is_not_in_source_inventory')
    raw = source.read_bytes()
    if not raw or len(raw) > 65536 or not 1 <= max_attempts <= 64 or not 1 <= timeout <= 300:
        raise ValueError('fixture_or_execution_budget_exceeded')
    work = root / 'artifacts/failure_reduction' / ('reduce-' + uuid.uuid4().hex[:10])
    project = work / 'source'
    snapshot(root, project, before)
    baseline, steps = [], []
    started = time.monotonic()
    def probe(data, label):
        owned_path(project, fixture).write_bytes(data)
        expected = {**before, fixture: digest(data)}
        result = verify_snapshot(project, work / label, test_targets=tests, timeout=timeout,
                                 pytest_plugins=pytest_plugins)
        if changed_files(root, before) or changed_files(project, expected):
            raise ValueError('source_changed_by_test_or_concurrent_edit')
        signature = failure_signature(result)
        return result, signature
    for index in range(2):
        result, signature = probe(raw, f'baseline-{index}')
        baseline.append({'result': result, 'signature': signature})
    expected = baseline[0]['signature']
    report = {'schema_version': 'failure_input_reduction.v1', 'fixture': fixture,
              'source_sha256': digest(raw), 'baseline': baseline, 'source_applied': False,
              'scope': 'same_test_collection_failure_type_and_message; review causal equivalence separately'}
    if not expected or baseline[1]['signature'] != expected:
        report.update(status='not_reproducible', reduced=False)
    else:
        def reproduces(data):
            result, signature = probe(data, f'candidate-{len(steps)}')
            same = signature == expected
            steps.append({'bytes': len(data), 'sha256': digest(data), 'same_failure': same, 'junit': result['junit']})
            return same
        reduced, attempts = minimize_bytes(raw, reproduces, max_attempts=max_attempts)
        # A selected reduction needs an independent final repeat as well.
        _, final = probe(reduced, 'final-repeat')
        valid = final == expected
        (work / 'reduced.fixture').write_bytes(reduced)
        report.update(status='reduced' if valid and len(reduced) < len(raw) else 'no_verified_reduction',
                      reduced=valid and len(reduced) < len(raw), original_bytes=len(raw), reduced_bytes=len(reduced),
                      attempts=attempts, steps=steps, candidate=str(work / 'reduced.fixture'), final_signature=final)
    report['elapsed_seconds'] = round(time.monotonic() - started, 3)
    report['receipt'] = str(work / 'report.json')
    (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def failure_signature(result: dict) -> list | None:
    if result.get('returncode') != 1 or any(check['returncode'] for check in result.get('checks', [])):
        return None
    path = Path(result.get('junit', ''))
    if not path.is_file():
        return None
    rows, failed = [], False
    for case in ET.parse(path).iter('testcase'):
        failure = case.find('failure')
        if case.find('error') is not None:
            return None
        failed |= failure is not None
        rows.append([case.get('classname'), case.get('name'),
                     'skipped' if case.find('skipped') is not None else 'failed' if failure is not None else 'passed',
                     failure.get('type') if failure is not None else None,
                     failure.get('message') if failure is not None else None])
    return sorted(rows, key=lambda row: (row[0] or '', row[1] or '')) if failed else None

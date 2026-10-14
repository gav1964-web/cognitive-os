"""Run a bounded synthetic calibration pilot using the configured L4.5 model."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.stage_finalization import finalize_stage
from tools._stage_finalization_cases import create_case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--cases', type=int, default=24, choices=range(1, 25))
    parser.add_argument('--case-index', type=int, action='append', choices=range(24),
                        help='Repeat selected calibration cases in a separate run')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    work = root / 'artifacts/stage_finalization_pilot' / ('pilot-' + uuid.uuid4().hex[:10])
    work.mkdir(parents=True)
    rows = []
    indices = sorted(set(args.case_index)) if args.case_index else list(range(args.cases))
    for index in indices:
        project = work / f'case-{index:02d}'
        case = create_case(project, index)
        start = time.perf_counter()
        result = finalize_stage(project, repair=True, apply=True, test_targets=['tests'],
                                work_root=work / 'runs', timeout=60)
        row = {**case, 'status': result['status'], 'reason': result.get('reason'),
               'expectation_met': result['status'] == case['expected'],
               'duration_seconds': round(time.perf_counter() - start, 3),
               'telemetry': result.get('telemetry', []), 'work_directory': result.get('work_directory'),
               'baseline_passed': result.get('baseline', {}).get('passing'),
               'patched_passed': result.get('verification', {}).get('passing'),
               'checks': result.get('checks', {}), 'source_applied': result['source_applied']}
        row['llm_failure_kind'] = result.get('llm_failure_kind')
        rows.append(row)
        report = {'schema_version': 'stage_finalization_pilot.v1', 'evaluation_split': 'synthetic_calibration',
                  'certification_allowed': False, 'production_generalization_measured': False,
                  'cases': rows, 'completed': len(rows) == len(indices),
                  'summary': {'attempted': len(rows), 'expectations_met': sum(r['expectation_met'] for r in rows),
                              'applied': sum(r['source_applied'] for r in rows),
                              'duration_seconds': round(sum(r['duration_seconds'] for r in rows), 3),
                              'total_tokens': sum(t.get('total_tokens') or 0 for r in rows for t in r['telemetry']),
                              'cost_usd': None, 'cost_note': 'Gateway tariff not configured; token usage is recorded.'}}
        (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'case': case['case_id'], 'status': row['status'], 'reason': row['reason'],
                          'seconds': row['duration_seconds'], 'report': str(work / 'report.json')}), flush=True)
    return 0 if all(row['expectation_met'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())

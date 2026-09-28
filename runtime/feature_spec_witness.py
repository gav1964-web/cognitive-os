"""Optional native discriminator for acceptance repairing a known rejected patch.

Use only when a behavioral regression witness is required, not when review asks
for documentation or preservation coverage. Passing this gate grants no approval.
"""
from pathlib import Path

from .feature_acceptance import probe, save, validate_spec
from .feature_workspace import copy_source, inventory, materialize_edits, owned_path


class RejectedCandidateWitness:
    def __init__(self, *, project, expected, candidate, frozen, allowed, work, python):
        if candidate.get('review', {}).get('decision') != 'reject':
            raise ValueError('quality_witness_requires_rejected_review')
        self.project, self.work, self.python = Path(project), Path(work), Path(python)
        self.expected, self.candidate, self.allowed = expected, candidate, allowed
        self.frozen = {t['path']: t['content'].encode('utf-8') for t in frozen}
        self.ordinal = 0

    def __call__(self, spec):
        if inventory(self.project) != self.expected:
            raise ValueError('quality_witness_original_source_changed')
        tests = validate_spec(spec, self.expected)
        if any(tests.get(name) != body for name, body in self.frozen.items()):
            raise ValueError('quality_witness_frozen_tests_changed')
        added = sorted(set(tests) - set(self.frozen))
        if not added:
            return [{'rejected_candidate_witness': 'Add separate tests exposing the reviewed behavioral defect.'}]
        self.ordinal += 1
        work = self.work / str(self.ordinal)
        project = work / 'project'
        edits = materialize_edits(self.project, self.expected, self.candidate['proposal']['edits'],
                                  self.allowed, frozen_tests=self.frozen)
        copy_source(self.project, project, self.expected)
        for name, body in {**self.frozen, **edits}.items():
            target = owned_path(project, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        if (set(self.candidate['candidate_hashes']) != set(self.frozen) | set(edits)
                or inventory(project) != {**self.expected, **self.candidate['candidate_hashes']}):
            raise ValueError('quality_witness_candidate_hash_mismatch')
        for name in added:
            target = owned_path(project, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tests[name])
        result = probe(project, work / 'checks', self.python, added, spec.get('environment', {}))
        counts = result['counts']
        valid = (result['source_unchanged'] and result['returncode'] == 1
                 and counts['failed'] > 0 and counts['failed'] == len(result['assertion_failures'])
                 and not counts['error'] and not counts['skipped'])
        save(work / 'report.json', {'status': 'witness_found' if valid else 'rejected',
             'added_tests': added, 'result': result, 'grants_approval': False})
        if inventory(self.project) != self.expected:
            raise ValueError('quality_witness_original_source_changed')
        if valid:
            return []
        return [{'rejected_candidate_witness': {
            'instruction': 'New tests must expose the reviewed defect in this rejected candidate through assertions. All-green tests do not distinguish it; setup/runtime failures and skips are not evidence. Preserve accepted tests. Fresh audit and full native qualification remain mandatory.',
            'counts': counts, 'assertion_failures': result['assertion_failures'],
            'returncode': result['returncode'], 'source_unchanged': result['source_unchanged'],
            'output_tail': result['output_tail'][-6000:]}}]

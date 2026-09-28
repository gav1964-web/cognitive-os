"""Give Reviewer the exact verified candidate diff, labeled against original reads."""
import difflib

from .feature_workspace import digest, owned_path


def candidate_patch(project, expected, edits):
    result = []
    for name, body in edits.items():
        original = owned_path(project, name).read_bytes() if name in expected else b''
        if name in expected and digest(original) != expected[name]:
            raise ValueError('feature_review_patch_stale_source')
        before = original.decode('utf-8-sig').replace('\r\n', '\n')
        after = body.decode('utf-8-sig').replace('\r\n', '\n')
        result.append({'path': name, 'source_sha256': expected.get(name),
                       'candidate_sha256': digest(body),
                       'unified_diff': ''.join(difflib.unified_diff(
                           before.splitlines(keepends=True), after.splitlines(keepends=True),
                           fromfile='original/' + name, tofile='candidate/' + name))})
    return result

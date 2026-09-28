import hashlib

import pytest

from plugins.development_quality.src.main import run


def probes(text):
    return run({'action': 'boundary_probes', 'sources': [{'path': 'bounds.py', 'content': text,
        'start': 1, 'sha256': hashlib.sha256(text.encode()).hexdigest()}]})['probes']


@pytest.mark.parametrize('source,old,wrong,masked,distinguishing', [
    ('def f(items, start, size):\n    return items[max(0,start):max(0,start)+size] if size > 0 else []\n',
     'size > 0', 'size != 0', ([1,2,3], 1, -1), ([1,2,3], 0, -1)),
    ('def f(value, low, high):\n    return low if value < 0 else min(value, high)\n',
     'value < 0', 'value != 0', (3, 2, 2), (3, 1, 5)),
])
def test_boundary_foil_requires_discriminating_combination(source, old, wrong, masked, distinguishing):
    rows = probes(source)
    foil = next(r for r in rows if r['old']==old and r['new']==wrong)
    reference, mutant = {}, {}
    exec(source, reference)
    exec(source.replace(foil['old'], foil['new']), mutant)
    assert reference['f'](*masked) == mutant['f'](*masked)
    assert reference['f'](*distinguishing) != mutant['f'](*distinguishing)
    assert foil['status'] == 'unvalidated_hypothesis'
    assert foil['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()


def test_bounded_probes_do_not_claim_unsupported_or_ambiguous_edits():
    assert probes('def f(x):\n    return 0 < x < 2\n') == []
    assert probes('def f(x):\n    return (x > 0) or (x > 0)\n') == []
    assert probes('this is not python!') == []
    rows = probes('def f(a,b,c,d,e):\n    return a>0 or b>0 or c>0 or d>0 or e>0\n')
    assert len(rows) == 8

from copy import deepcopy
from plugins.development_quality.src.main import run


def repair(value, sources):
    return run({'action':'repair_citations', 'artifact':value, 'sources':sources})


def test_only_unique_exact_location_changes_and_finding_is_untouched():
    raw={'evidence':[{'path':'engine.py','start':20,'end':20,
                     'quote':'return value + 1','finding':'unverified causal assertion'}]}
    before=deepcopy(raw)
    result=repair(raw,[{'path':'engine.py','start':4,'content':'def f(value):\n    return value + 1\n'}])
    assert raw==before and result['changes']
    row=result['artifact']['evidence'][0]
    assert (row['start'],row['end'])==(5,5)
    assert row['finding']==before['evidence'][0]['finding']
    assert result['grants_approval'] is False


def test_ambiguous_absent_disjoint_or_conflicting_source_is_not_repaired():
    raw={'evidence':[{'path':'engine.py','start':10,'end':10,'quote':'a\nb'}]}
    cases=[[],[{'path':'other.py','start':1,'content':'a\nb'}],
        [{'path':'engine.py','start':1,'content':'a\nb\na\nb'}],
        [{'path':'engine.py','start':1,'content':'a'}, {'path':'engine.py','start':3,'content':'b'}],
        [{'path':'engine.py','start':1,'content':'a\nb'}, {'path':'engine.py','start':1,'content':'different'}]]
    for sources in cases:
        assert repair(raw,sources)['artifact']==raw


def test_valid_broad_range_is_not_narrowed():
    raw={'evidence':[{'path':'engine.py','start':1,'end':3,'quote':'b'}]}
    assert not repair(raw,[{'path':'engine.py','start':1,'content':'a\nb\nc'}])['changes']

from copy import deepcopy
import pytest
from plugins.development_quality.src.source_evidence import validate_evidence, review_has_counterexample


def reference():
    return {'evidence': [{'path': 'a.py', 'start': 10, 'end': 11,
        'quote': 'return x', 'symbol': 'f', 'finding': 'Returns the argument.'}]}


def test_citations_are_bound_to_selected_source_lines():
    src = [{'path':'a.py','start':10,'content':'def f(x):\n    return x\n'}]
    assert not validate_evidence(reference(), src)
    for change in ({'start':9}, {'end':12}, {'quote':'return y'}, {'symbol':'g'}, {'path':'b.py'}):
        value = reference()
        value['evidence'][0].update(change)
        assert validate_evidence(value, src)
    assert not validate_evidence(reference(), [
        {'path':'a.py','start':10,'content':'def f(x):'},
        {'path':'a.py','start':11,'content':'    return x'}])


def test_missing_quotes_and_malformed_ranges_do_not_pass():
    src = [{'path':'a.py','start':10,'content':'def f(x):\n    return x'}]
    for change in ({'quote':''}, {'start':True}, {'end':9}, {'quote':None}):
        value = reference()
        value['evidence'][0].update(change)
        assert validate_evidence(value, src)
    assert not validate_evidence({'evidence': []}, [])  # Historical empty evidence is not certification.


def test_only_concrete_rejected_behavior_requests_a_witness():
    row = {'decision':'reject','counterexamples':[{
        'input':0,'expected':'zero','observed':'0','goal_clause':'zero labels'}]}
    assert review_has_counterexample(row)
    for key in row['counterexamples'][0]:
        bad = deepcopy(row)
        del bad['counterexamples'][0][key]
        assert not review_has_counterexample(bad)
    assert not review_has_counterexample({**row,'decision':'approve'})
    assert not review_has_counterexample({'decision':'reject','reason':'need docs'})


def test_wrong_range_gets_exact_location_but_is_not_accepted_or_rewritten():
    sources = [{'path':'a.py','start':10,'content':'def f(x):\n    return x\n'}]
    value = reference()
    value['evidence'][0].update(end=10, symbol=None)
    before = deepcopy(value)
    issues = validate_evidence(value, sources)
    assert len(issues) == 1 and 'supplied lines 11-11' in issues[0]
    assert value == before
    value['evidence'][0].update(start=11, end=11)
    assert not validate_evidence(value, sources)


def test_hint_does_not_join_unread_gaps_or_choose_ambiguous_quote():
    value = reference()
    value['evidence'][0].update(end=10, symbol=None, quote='return x\nreturn y')
    sources = [{'path':'a.py','start':10,'content':'pass\nreturn x'},
               {'path':'a.py','start':13,'content':'return y'}]
    assert 'no location' in validate_evidence(value, sources)[0]
    value['evidence'][0]['quote'] = 'return x'
    sources.append({'path':'a.py','start':20,'content':'return x'})
    assert 'multiple locations' in validate_evidence(value, sources)[0]
    assert validate_evidence(value, sources)


def test_quote_hint_uses_supplied_line_offsets_and_multiline_span():
    value = reference()
    value['evidence'][0].update(start=31, end=31, symbol=None, quote='x = 1\n    return x')
    sources = [{'path':'a.py','start':31,'content':'def f():\n    x = 1\n    return x'}]
    assert 'supplied lines 32-33' in validate_evidence(value, sources)[0]

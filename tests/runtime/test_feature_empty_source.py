import pytest

from runtime.feature_workspace import inventory, merge_reads, read_sources


def test_empty_package_read_survives_merge_and_checkpoint_re_read(tmp_path):
    (tmp_path/'pkg').mkdir()
    (tmp_path/'pkg/__init__.py').write_bytes(b'')
    (tmp_path/'pkg/api.py').write_text('def api():\n    return 1\n')
    expected=inventory(tmp_path)
    rows=read_sources(tmp_path,expected,[{'path':'pkg/__init__.py','start':1,'end':1},
                                       {'path':'pkg/api.py'}])
    empty=rows[0]
    assert empty['total_lines']==0 and empty['content']=='' and empty['eof']
    assert empty['end']==0 and not empty['truncated']
    merged=merge_reads(rows,rows)
    assert len(merged)==2 and any(r['path']=='pkg/__init__.py' for r in merged)
    reread=read_sources(tmp_path,expected,[{'path':r['path'],'start':r['start'],'end':r['end']} for r in merged])
    assert [(r['path'],r['content']) for r in reread]==[(r['path'],r['content']) for r in rows]
    assert read_sources(tmp_path,expected,[{'path':'pkg/__init__.py'}])[0]['total_lines']==0


def test_empty_support_keeps_invalid_ranges_and_oversized_lines_rejected(tmp_path):
    (tmp_path/'empty.py').write_bytes(b'')
    (tmp_path/'large.py').write_text('x = '+repr('a'*1000)+'\n')
    expected=inventory(tmp_path)
    with pytest.raises(ValueError,match='feature_read_range'):
        read_sources(tmp_path,expected,[{'path':'empty.py','start':2,'end':2}])
    with pytest.raises(ValueError,match='feature_single_line_exceeds_read_budget'):
        read_sources(tmp_path,expected,[{'path':'large.py'}],max_bytes=20)

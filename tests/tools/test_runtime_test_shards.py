from __future__ import annotations

from tools.runtime_test_shards import _indexes, _shard_tests


def test_runtime_test_shards_distribute_without_loss():
    tests = [f"tests/runtime/test_sample.py::test_{index}" for index in range(10)]
    shards = [_shard_tests(tests, index, 3) for index in range(3)]

    assert sorted(test for shard in shards for test in shard) == sorted(tests)
    assert max(len(shard) for shard in shards) - min(len(shard) for shard in shards) <= 1


def test_runtime_test_shards_select_single_index():
    assert _indexes(4, None) == [0, 1, 2, 3]
    assert _indexes(4, 2) == [2]

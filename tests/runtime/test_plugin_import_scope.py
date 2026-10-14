"""Cross-workspace calls must not poison the host's subsequent plugin imports."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib
from pathlib import Path
import sys
import threading

import pytest

from runtime.plugin_import_scope import plugin_import_scope, plugin_import_session


def _workspace(root, value):
    package = root / 'plugins'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    (package / 'scope_probe.py').write_text(f'value = {value!r}\n')
    return root


def _plugins():
    return {k: v for k, v in sys.modules.copy().items()
            if k == 'plugins' or k.startswith('plugins.')}


@pytest.mark.parametrize('fail', [False, True])
def test_scope_restores_exact_host_modules_and_path(tmp_path, fail):
    from plugins.project_description.src import main
    host, paths = _plugins(), list(sys.path)
    root = _workspace(tmp_path / 'workspace', 'target')
    try:
        with plugin_import_scope(root):
            module = importlib.import_module('plugins.scope_probe')
            assert module.value == 'target'
            assert Path(module.__file__).is_relative_to(root)
            if fail:
                raise LookupError('plugin failed')
    except LookupError:
        assert fail
    assert _plugins() == host and sys.path == paths
    assert importlib.import_module('plugins.project_description.src.main') is main


def test_concurrent_workspace_calls_keep_lazy_imports_in_their_own_root(tmp_path):
    roots = [_workspace(tmp_path / str(i), i) for i in range(2)]
    paths, host = list(sys.path), _plugins()
    start = threading.Barrier(2)
    def run(root):
        start.wait(timeout=5)
        with plugin_import_scope(root):
            return importlib.import_module('plugins.scope_probe').value
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, roots)) == [0, 1]
    assert _plugins() == host and sys.path == paths


def test_pipeline_retains_retry_state_and_resets_it_for_the_next_run(tmp_path):
    root = _workspace(tmp_path / 'workspace', 0)
    @plugin_import_session
    def pipeline(root):
        with plugin_import_scope(root):
            module = importlib.import_module('plugins.scope_probe')
            assert module.value == 0
            module.value += 1
        with plugin_import_scope(root):
            assert importlib.import_module('plugins.scope_probe') is module
            assert module.value == 1
    pipeline(root)
    pipeline(root)


@pytest.mark.asyncio
async def test_both_executors_leave_host_knowledge_callable(runtime_workspace):
    from plugins.project_description.src import main
    from runtime.async_executor import execute_pipeline_async
    from runtime.executor import execute_pipeline
    from runtime.pipeline import load_pipeline
    from runtime.registry import CapabilityRegistry
    root = runtime_workspace
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = load_pipeline(root / 'pipelines/fetch_parse_save.json')
    host, paths = _plugins(), list(sys.path)
    payload = {'url': 'mock://ok', 'output_path': 'artifacts/outputs/scope.json'}
    for invoke in (execute_pipeline, execute_pipeline_async):
        result = invoke(root, pipeline, payload)
        if asyncio.iscoroutine(result):
            result = await result
        assert result['status'] == 'ok'
        assert _plugins() == host and sys.path == paths
        assert importlib.import_module('plugins.project_description.src.main') is main
        retry = invoke(root, pipeline, {**payload, 'url': 'mock://transient_once'})
        if asyncio.iscoroutine(retry):
            retry = await retry
        assert retry['status'] == 'ok'
        assert retry['outputs']['parse']['title'] == 'Recovered After Retry'
        assert _plugins() == host and sys.path == paths

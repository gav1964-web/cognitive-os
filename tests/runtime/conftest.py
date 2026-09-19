from __future__ import annotations

import shutil
from pathlib import Path
from urllib import request, error
from urllib.parse import urlsplit

import pytest


@pytest.fixture(scope='session', autouse=True)
def _offline_inference_session():
    """Runtime regressions use scripted model responses or the offline fallback.

    Patch the transport boundary so aliases of call_json_chat are covered too.
    A test can still replace urlopen with its own fake. Live measurements belong
    in the separately budgeted experiment runners, outside this pytest scope.
    """
    original = request.urlopen
    blocked = []

    def open_without_inference(value, *args, **kwargs):
        url = value.full_url if isinstance(value, request.Request) else str(value)
        if urlsplit(url).path.rstrip('/').endswith('/chat/completions'):
            blocked.append(urlsplit(url).hostname)
            raise error.URLError('live inference disabled in runtime regression tests')
        return original(value, *args, **kwargs)

    # Session setup precedes module-scoped fixtures, which can also invoke roles.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(request, 'urlopen', open_without_inference)
        yield blocked


@pytest.fixture()
def offline_inference(_offline_inference_session):
    _offline_inference_session.clear()
    return _offline_inference_session


@pytest.fixture()
def runtime_workspace(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "runtime_workspace"
    for name in ("config", "knowledge", "pipelines", "plugins", "registry", "roles", "runtime", "tools"):
        shutil.copytree(source / name, workspace / name)
    shutil.copy2(source / "run_mvp.py", workspace / "run_mvp.py")
    return workspace

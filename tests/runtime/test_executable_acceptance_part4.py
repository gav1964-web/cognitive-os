from __future__ import annotations

import asyncio
from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from tests.runtime.test_executable_acceptance import _plan


def test_executable_acceptance_accepts_done_future_result(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "import asyncio\n\n"
        "def nudge():\n"
        "    loop = asyncio.new_event_loop()\n"
        "    future = loop.create_future()\n"
        "    future.set_result(None)\n"
        "    return future\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:nudge", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_creates_missing_event_loop_for_future(tmp_path: Path):
    asyncio.run(asyncio.sleep(0))
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "import asyncio\n\n"
        "def nudge():\n"
        "    future = asyncio.Future()\n"
        "    future.set_result(None)\n"
        "    return future\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:nudge", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_source_isolated_method_keeps_module_helper_closure(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text(
        "raise RuntimeError('import-time side effect')\n\n"
        "PREFIX = 'seen:'\n\n"
        "def helper(value):\n"
        "    return PREFIX + value\n\n"
        "class Handler:\n"
        "    def handle(self, url):\n"
        "        return {'parsed_url': helper(url)}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/module.py:handle", {"url": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["src/pkg/module.py:handle"]


def test_source_isolated_method_uses_profiled_local_framework_helpers(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "gradio"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "blocks.py").write_text(
        "from collections.abc import Sequence, Set\n"
        "from gradio import utils\n"
        "from gradio.block_function import BlockFunction\n"
        "from gradio.context import LocalContext\n"
        "from gradio.helpers import special_args\n"
        "from gradio.utils import check_function_inputs_match\n\n"
        "raise RuntimeError('full framework import is too heavy')\n\n"
        "class BlocksConfig:\n"
        "    def set_event_trigger(self, targets, fn, inputs, outputs, trigger_mode='once', api_name=None):\n"
        "        if isinstance(inputs, Set):\n"
        "            inputs_as_dict = True\n"
        "        else:\n"
        "            inputs_as_dict = False\n"
        "            if inputs is None:\n"
        "                inputs = []\n"
        "            elif not isinstance(inputs, Sequence):\n"
        "                inputs = [inputs]\n"
        "        if fn is not None:\n"
        "            check_function_inputs_match(fn, inputs, inputs_as_dict)\n"
        "        _, progress_index, event_data_index, component_prop_indices = special_args(fn)\n"
        "        rendered_in = LocalContext.renderable.get(None)\n"
        "        api_name = utils.append_unique_suffix(api_name or fn.__name__, [])\n"
        "        block_fn = BlockFunction(fn, inputs, outputs, _id=self.fn_id, api_name=api_name, rendered_in=rendered_in)\n"
        "        self.fns[self.fn_id] = block_fn\n"
        "        self.fn_id += 1\n"
        "        return block_fn, block_fn._id\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/gradio/blocks.py:set_event_trigger", {"targets": [], "inputs": [], "outputs": []}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["src/gradio/blocks.py:set_event_trigger"]

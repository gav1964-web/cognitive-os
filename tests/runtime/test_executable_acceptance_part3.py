from __future__ import annotations

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.test_plan_builder import build_test_plan
from tests.runtime.test_executable_acceptance import _plan


def test_executable_acceptance_stubs_bounded_optional_import_chain(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    imports = "\n".join(f"import optional_missing_{index}" for index in range(4))
    (package / "parser.py").write_text(
        f"{imports}\n\n"
        "def parse(value):\n"
        "    return {'parsed_url': value}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/pkg/parser.py:parse", {"value": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dependency_stub_targets"]["src/pkg/parser.py:parse"] == [
        "optional_missing_0",
        "optional_missing_1",
        "optional_missing_2",
        "optional_missing_3",
    ]


def test_executable_acceptance_invokes_positional_only_defaults(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "def path_template(template, /, **kwargs):\n"
        "    return template.format(**kwargs) if kwargs else template\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:path_template", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:path_template"] == {"template": "sample"}


def test_executable_acceptance_executes_profiled_no_arg_method_with_surplus_payload(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "class Queue:\n"
        "    def task_done(self):\n"
        "        with self.all_tasks_done:\n"
        "            self.unfinished_tasks -= 1\n"
        "            if self.unfinished_tasks == 0:\n"
        "                self.all_tasks_done.notify_all()\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:task_done", {"message": "sample", "runtime_context": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["dropped_surplus_payload_targets"] == ["module.py:task_done"]


def test_executable_acceptance_rejects_wrong_declared_result_type(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text("def status():\n    return 1\n", encoding="utf-8")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "module.py:status",
                        "kind": "positive_contract_case",
                        "given": {},
                        "expect": {"result": "str"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "side_effect_boundary",
                        "target": "module.py:status",
                        "kind": "side_effect_scope_case",
                        "given": {},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ]
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "meta_only"
    assert result["summary"]["skipped_reason_counts"] == {"positive_sample_execution_failed": 1}


def test_executable_acceptance_uses_archive_method_state_profile(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "class AbstractArchiveFileSystem:\n"
        "    def ls(self, path, detail=True, **kwargs):\n"
        "        self._get_dirs()\n"
        "        return sorted(self.dir_cache.values(), key=lambda item: item['name'])\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:ls", {"path": ""}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert "module.py:ls" in result["summary"]["method_instance_attributes"]


def test_executable_acceptance_uses_hatch_environment_fixture(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "module.py").write_text(
        "def prepare_lock_generation_state(environment):\n"
        "    if environment.skip_install:\n"
        "        return None\n"
        "    return {'result': list(environment.dependencies)}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("module.py:prepare_lock_generation_state", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["argument_defaults"]["module.py:prepare_lock_generation_state"]["environment"] == {
        "__fixture__": "hatch_environment_minimal"
    }


def test_executable_acceptance_profiles_hatch_virtual_environment_import(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "hatch" / "env"
    package.mkdir(parents=True)
    (project / "src" / "hatch" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "lock.py").write_text(
        "from pathlib import Path\n\n"
        "def prepare_lock_generation_state(environment):\n"
        "    from hatch.env.virtual import VirtualEnvironment\n"
        "    layered = isinstance(environment, VirtualEnvironment)\n"
        "    return {'dependencies': list(environment.dependencies), 'layered': layered, 'root': Path(environment.root)}\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/hatch/env/lock.py:prepare_lock_generation_state", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["callable_harness_count"] == 1
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_runs_async_void_side_effect_with_datasette_fixture(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "datasette"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "stored_queries.py").write_text(
        "async def add_query(datasette, database, name, sql):\n"
        "    db = datasette.get_internal_database()\n"
        "    await db.execute_write('insert into queries values (?, ?, ?)', [database, name, sql])\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "datasette/stored_queries.py:add_query",
                        "kind": "positive_contract_case",
                        "given": {"datasette": {"__fixture__": "datasette_minimal"}, "database": "data", "name": "value", "sql": "select 1"},
                        "expect": {"completed": True},
                        "oracle": "call_completes_and_side_effect_boundary_is_declared",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "side_effect_boundary",
                        "target": "datasette/stored_queries.py:add_query",
                        "kind": "side_effect_scope_case",
                        "given": {"declared_scope": "writable_scope_only"},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    }
                ]
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_test_plan_builder_uses_completion_expectation_for_void_side_effect():
    plan = build_test_plan(
        technical_spec={"acceptance_criteria": [{"id": "AC-001", "criterion": "query is stored"}]},
        implementation_plan={
            "implementation_target": {"candidate": "datasette/stored_queries.py:add_query"},
            "patch_scope": ["datasette/stored_queries.py:add_query"],
            "writable_scope": ["datasette/stored_queries.py:add_query"],
            "contract_binding": {
                "binding_status": "bound_to_extraction_contract",
                "input_contract": {"datasette": "InferredDatasette", "database": "str", "name": "str", "sql": "str"},
                "output_contract": {"result": "VoidSideEffect"},
            },
        },
    )

    obligation = plan["executable_acceptance"]["obligations"][0]
    assert obligation["expect"] == {"completed": True}
    assert obligation["given"]["datasette"] == {"__fixture__": "datasette_minimal"}


def test_executable_acceptance_uses_qdrant_local_collection_fixture(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "qdrant_client" / "local"
    package.mkdir(parents=True)
    (project / "qdrant_client" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "local_collection.py").write_text(
        "class LocalCollection:\n"
        "    def search(self, query_vector, query_filter=None, limit=10, offset=None, with_payload=True, with_vectors=False, score_threshold=None):\n"
        "        assert self.vectors[''][0][0] == query_vector[0]\n"
        "        assert query_filter is None\n"
        "        assert score_threshold is None\n"
        "        return [{'id': self.ids_inv[0], 'score': 1.0, 'payload': self.payload[0]}][:limit]\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("qdrant_client/local/local_collection.py:search", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["method_instance_attributes"]["qdrant_client/local/local_collection.py:search"]["vectors"] == {
        "__fixture__": "qdrant_dense_vectors"
    }


def test_executable_acceptance_uses_chroma_async_search_client_fixture(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "chromadb" / "api" / "models"
    package.mkdir(parents=True)
    (project / "chromadb" / "__init__.py").write_text("", encoding="utf-8")
    (project / "chromadb" / "api" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "AsyncCollection.py").write_text(
        "def maybe_cast_one_to_many(value):\n"
        "    return value\n\n"
        "class AsyncCollection:\n"
        "    @property\n"
        "    def id(self):\n"
        "        return self._model.id\n"
        "    @property\n"
        "    def tenant(self):\n"
        "        return self._model.tenant\n"
        "    @property\n"
        "    def database(self):\n"
        "        return self._model.database\n"
        "    def _embed_search_string_queries(self, search):\n"
        "        return search\n"
        "    async def search(self, searches, read_level='sample'):\n"
        "        searches_list = maybe_cast_one_to_many(searches) or []\n"
        "        embedded_searches = [self._embed_search_string_queries(search) for search in searches_list]\n"
        "        return await self._client._search(collection_id=self.id, searches=embedded_searches, tenant=self.tenant, database=self.database, read_level=read_level)\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("chromadb/api/models/AsyncCollection.py:search", {}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    attrs = result["summary"]["method_instance_attributes"]["chromadb/api/models/AsyncCollection.py:search"]
    assert attrs["_client"] == {"__fixture__": "chroma_search_client"}
    assert attrs["_model"] == {"__fixture__": "chroma_collection_model"}


def test_executable_acceptance_source_isolates_decorated_cli_command(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "sqlite_utils"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text(
        "from missing_decorator import command\n\n"
        "@command()\n"
        "def triggers(ctx, path):\n"
        "    return ctx.invoke(None, path=path)\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("sqlite_utils/cli.py:triggers", {"ctx": "sample", "path": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
    assert result["summary"]["source_isolated_targets"] == ["sqlite_utils/cli.py:triggers"]


def test_executable_acceptance_source_isolates_lazy_image_template_function(tmp_path: Path):
    project = tmp_path / "project"
    package = project / "src" / "_skimage2" / "feature"
    shared = project / "src" / "_skimage2" / "_shared"
    package.mkdir(parents=True)
    shared.mkdir(parents=True)
    (project / "src" / "_skimage2" / "__init__.py").write_text(
        "import lazy_loader as _lazy\n__getattr__, *_ = _lazy.attach_stub(__name__, __file__)\n",
        encoding="utf-8",
    )
    (shared / "__init__.py").write_text("", encoding="utf-8")
    (shared / "utils.py").write_text("def check_nD(value, dims): pass\n", encoding="utf-8")
    (package / "template.py").write_text(
        "import numpy as np\nfrom _skimage2._shared.utils import check_nD\n\n"
        "def match_template(image, template, pad_input=False, mode='constant', constant_values=0):\n"
        "    check_nD(image, (2, 3))\n"
        "    return np.zeros_like(image, dtype='float32') + template.mean()\n",
        encoding="utf-8",
    )

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_plan("src/_skimage2/feature/template.py:match_template", {"image": [[1.0]], "template": "sample"}, malformed=False),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"
